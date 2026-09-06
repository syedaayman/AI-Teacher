import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidSessionStateError,
    SessionNotFoundError,
)
from app.db.repository import LearnerRepository
from app.db.session import get_db_session
from app.schemas.session import (
    LessonSessionState,
    SessionStatus,
    TeachingStep,
)

logger = logging.getLogger(__name__)


class SessionService:
    """Manages lifecycle, in-memory caching, and database persistence of teaching sessions."""

    def __init__(self):
        self._cache: Dict[str, LessonSessionState] = {}

    async def create_session(
        self,
        state: LessonSessionState,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Register a new session in cache and persist to database."""
        self._cache[state.session_id] = state

        async def _persist(s: AsyncSession):
            repo = LearnerRepository(s)
            await repo.create_session_log(
                session_id=state.session_id,
                learner_id=state.learner_id,
                lesson_id=state.lesson_id,
                topic=state.topic,
                material_id=state.material_id,
                difficulty=state.difficulty.value,
                language=state.language.value,
                available_time_minutes=state.time_budget_minutes,
                desired_depth=state.desired_depth,
                session_metadata=state.model_dump(mode="json"),
            )
            await repo.log_learning_event(
                learner_id=state.learner_id,
                session_id=state.session_id,
                concept_id=state.current_concept_id,
                event_type="SESSION_STARTED",
                payload={
                    "topic": state.topic,
                    "concepts": state.concepts,
                    "time_budget": state.time_budget_minutes,
                    "depth": state.desired_depth,
                },
            )

        if db_session is not None:
            await _persist(db_session)
        else:
            async with get_db_session() as s:
                await _persist(s)

        return state

    async def get_session(
        self,
        session_id: str,
        db_session: Optional[AsyncSession] = None,
        ensure_active: bool = False,
    ) -> LessonSessionState:
        """Fetch session from cache or reconstruct from database."""
        if not session_id or not session_id.strip():
            raise SessionNotFoundError("session_id cannot be empty.")

        clean_id = session_id.strip()
        state = self._cache.get(clean_id)

        if state is None:
            async def _fetch(s: AsyncSession) -> Optional[LessonSessionState]:
                repo = LearnerRepository(s)
                sess_log = await repo.get_session_log(clean_id)
                if sess_log and sess_log.session_metadata:
                    try:
                        return LessonSessionState.model_validate(sess_log.session_metadata)
                    except Exception as ex:
                        logger.error("Failed to reconstruct LessonSessionState from metadata: %s", ex)
                return None

            if db_session is not None:
                state = await _fetch(db_session)
            else:
                async with get_db_session() as s:
                    state = await _fetch(s)

            if state is None:
                raise SessionNotFoundError(f"Teaching session '{clean_id}' not found.")

            self._cache[clean_id] = state

        if ensure_active and (state.is_completed or state.status == SessionStatus.COMPLETED):
            raise InvalidSessionStateError(
                f"Session '{clean_id}' has already completed and cannot be restored as an active session."
            )

        return state

    async def get_active_session(
        self,
        session_id: str,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Fetch active session from cache or database, guaranteeing it is active."""
        return await self.get_session(session_id, db_session=db_session, ensure_active=True)

    async def save_session(
        self,
        state: LessonSessionState,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Update session state in cache and persist modifications to database."""
        state.updated_at = datetime.now(timezone.utc)
        self._cache[state.session_id] = state

        async def _save(s: AsyncSession):
            repo = LearnerRepository(s)
            sess_log = await repo.get_session_log(state.session_id)
            if sess_log:
                sess_log.status = state.status.value
                sess_log.current_concept_id = state.current_concept_id
                sess_log.current_difficulty = state.difficulty.value
                sess_log.remaining_time_minutes = state.remaining_time_minutes
                sess_log.step_count = state.step_count
                sess_log.session_metadata = state.model_dump(mode="json")
                if state.ended_at:
                    sess_log.ended_at = state.ended_at
                await s.flush()
            else:
                # If record didn't exist, create it
                await repo.create_session_log(
                    session_id=state.session_id,
                    learner_id=state.learner_id,
                    lesson_id=state.lesson_id,
                    topic=state.topic,
                    material_id=state.material_id,
                    difficulty=state.difficulty.value,
                    language=state.language.value,
                    available_time_minutes=state.time_budget_minutes,
                    desired_depth=state.desired_depth,
                    session_metadata=state.model_dump(mode="json"),
                )

        if db_session is not None:
            await _save(db_session)
        else:
            async with get_db_session() as s:
                await _save(s)

        return state

    async def end_session(
        self,
        session_id: str,
        status: SessionStatus = SessionStatus.COMPLETED,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Mark a session complete and log final event."""
        state = await self.get_session(session_id, db_session=db_session)
        state.status = status
        state.current_step = TeachingStep.COMPLETE
        state.ended_at = datetime.now(timezone.utc)

        async def _finish(s: AsyncSession):
            repo = LearnerRepository(s)
            if state.lesson_id:
                try:
                    await repo.record_lesson_completion(state.learner_id, state.lesson_id)
                except Exception as ex:
                    logger.warning("Could not record lesson completion: %s", ex)

            await repo.log_learning_event(
                learner_id=state.learner_id,
                session_id=state.session_id,
                event_type="SESSION_COMPLETED",
                payload={
                    "status": status.value,
                    "completed_concepts": state.completed_concepts,
                    "total_steps": state.step_count,
                    "remaining_time": state.remaining_time_minutes,
                },
            )

        if db_session is not None:
            await _finish(db_session)
        else:
            async with get_db_session() as s:
                await _finish(s)

        await self.save_session(state, db_session=db_session)
        return state

    async def get_active_session_for_learner(
        self,
        learner_id: str,
        db_session: Optional[AsyncSession] = None,
    ) -> Optional[LessonSessionState]:
        """Find any ongoing active session for a given learner."""
        # Check cache first
        for state in self._cache.values():
            if state.learner_id == learner_id and state.status == SessionStatus.ACTIVE:
                return state

        async def _check_db(s: AsyncSession) -> Optional[LessonSessionState]:
            repo = LearnerRepository(s)
            active_log = await repo.get_active_session_log(learner_id)
            if active_log and active_log.session_metadata:
                try:
                    return LessonSessionState.model_validate(active_log.session_metadata)
                except Exception as ex:
                    logger.error("Failed to parse active session log metadata: %s", ex)
            return None

        if db_session is not None:
            return await _check_db(db_session)
        else:
            async with get_db_session() as s:
                return await _check_db(s)


session_service = SessionService()
