from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    InvalidLearnerProfileError,
    InvalidProfileUpdateError,
    LearnerNotFoundError,
)
from app.db.models import (
    AssessmentAttempt,
    ConceptMasteryRecord,
    Learner,
    LearnerPreference,
    LearningEvent,
    SessionLog,
    utc_now,
)
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.learner import LearnerProfile, SupportedLanguage
from app.schemas.lesson import DifficultyLevel


class LearnerRepository:
    """Asynchronous repository for database-backed Learner data operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_learner(
        self,
        learner_id: str,
        name: Optional[str] = None,
        preferred_language: str = "english",
        preferred_difficulty: str = "intermediate",
        learning_goal: Optional[str] = None,
        teaching_style: str = "interactive",
        available_time_minutes: int = 20,
        desired_depth: str = "standard",
        total_lessons: int = 0,
    ) -> Learner:
        """Create and persist a new Learner and initial LearnerPreference."""
        clean_id = (learner_id or "").strip()
        if not clean_id:
            raise InvalidLearnerProfileError("learner_id cannot be empty or whitespace.")

        existing = await self.get_learner(clean_id)
        now = utc_now()
        if existing is not None:
            existing.name = name.strip() if name else None
            existing.total_lessons = max(0, total_lessons)
            existing.completed_lessons = []
            existing.assessment_count = 0
            existing.average_score = 0.0
            existing.overall_mastery = 0.0
            existing.updated_at = now
            if existing.preference:
                existing.preference.preferred_language = str(preferred_language).lower()
                existing.preference.preferred_difficulty = str(preferred_difficulty).lower()
                existing.preference.learning_goal = learning_goal.strip() if learning_goal else None
                existing.preference.teaching_style = str(teaching_style).lower()
                existing.preference.available_time_minutes = available_time_minutes
                existing.preference.desired_depth = str(desired_depth).lower()
                existing.preference.updated_at = now
            await self.session.flush()
            return await self.get_learner(clean_id)

        learner = Learner(
            id=clean_id,
            name=name.strip() if name else None,
            total_lessons=max(0, total_lessons),
            completed_lessons=[],
            assessment_count=0,
            average_score=0.0,
            overall_mastery=0.0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(learner)

        pref = LearnerPreference(
            learner_id=clean_id,
            preferred_language=str(preferred_language).lower(),
            preferred_difficulty=str(preferred_difficulty).lower(),
            learning_goal=learning_goal.strip() if learning_goal else None,
            teaching_style=str(teaching_style).lower(),
            available_time_minutes=available_time_minutes,
            desired_depth=str(desired_depth).lower(),
            created_at=now,
            updated_at=now,
        )
        self.session.add(pref)
        await self.session.flush()
        return await self.get_learner(clean_id)



    async def get_learner(self, learner_id: str) -> Optional[Learner]:
        """Fetch a Learner with preference and concept masteries eagerly loaded."""
        clean_id = (learner_id or "").strip()
        if not clean_id:
            return None

        stmt = (
            select(Learner)
            .where(Learner.id == clean_id)
            .options(
                selectinload(Learner.preference),
                selectinload(Learner.concept_masteries),
            )
            .execution_options(populate_existing=True)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


    async def get_or_create_learner(
        self,
        learner_id: str,
        name: Optional[str] = None,
        preferred_language: str = "english",
        preferred_difficulty: str = "intermediate",
        learning_goal: Optional[str] = None,
    ) -> Learner:
        """Get existing learner or initialize a new one."""
        learner = await self.get_learner(learner_id)
        if learner is None:
            learner = await self.create_learner(
                learner_id=learner_id,
                name=name,
                preferred_language=preferred_language,
                preferred_difficulty=preferred_difficulty,
                learning_goal=learning_goal,
            )
        return learner

    async def update_preferences(
        self,
        learner_id: str,
        preferred_language: Optional[str] = None,
        preferred_difficulty: Optional[str] = None,
        learning_goal: Optional[str] = None,
        teaching_style: Optional[str] = None,
        available_time_minutes: Optional[int] = None,
        desired_depth: Optional[str] = None,
    ) -> LearnerPreference:
        """Update instructional preferences for an existing learner."""
        learner = await self.get_learner(learner_id)
        if learner is None:
            raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

        pref = learner.preference
        if pref is None:
            pref = LearnerPreference(learner_id=learner.id)
            self.session.add(pref)

        if preferred_language is not None:
            pref.preferred_language = str(preferred_language).lower()
        if preferred_difficulty is not None:
            pref.preferred_difficulty = str(preferred_difficulty).lower()
        if learning_goal is not None:
            pref.learning_goal = learning_goal.strip() if learning_goal else None
        if teaching_style is not None:
            pref.teaching_style = str(teaching_style).lower()
        if available_time_minutes is not None:
            pref.available_time_minutes = max(1, available_time_minutes)
        if desired_depth is not None:
            pref.desired_depth = str(desired_depth).lower()

        now = utc_now()
        pref.updated_at = now
        learner.updated_at = now
        await self.session.flush()
        return pref

    async def upsert_concept_mastery(
        self,
        learner_id: str,
        concept_mastery: ConceptMastery,
    ) -> ConceptMasteryRecord:
        """Upsert a concept mastery record and recompute the learner's overall mastery."""
        if not concept_mastery or not concept_mastery.concept_id:
            raise InvalidProfileUpdateError("Valid concept_mastery is required.")

        learner = await self.get_learner(learner_id)
        if learner is None:
            raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

        stmt = select(ConceptMasteryRecord).where(
            ConceptMasteryRecord.learner_id == learner.id,
            ConceptMasteryRecord.concept_id == concept_mastery.concept_id,
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        now = utc_now()
        last_rev = None
        if getattr(concept_mastery, "last_reviewed_at", None):
            try:
                last_rev = datetime.fromisoformat(concept_mastery.last_reviewed_at.replace("Z", "+00:00"))
            except Exception:
                last_rev = now

        next_due = None
        if getattr(concept_mastery, "next_review_due_at", None):
            try:
                next_due = datetime.fromisoformat(concept_mastery.next_review_due_at.replace("Z", "+00:00"))
            except Exception:
                next_due = None

        if record is None:
            record = ConceptMasteryRecord(
                learner_id=learner.id,
                concept_id=concept_mastery.concept_id,
                mastery_score=concept_mastery.mastery_score,
                mastery_level=concept_mastery.mastery_level.value,
                confidence=concept_mastery.confidence,
                attempts=concept_mastery.attempts,
                correct_attempts=concept_mastery.correct_attempts,
                partial_attempts=concept_mastery.partial_attempts,
                incorrect_attempts=concept_mastery.incorrect_attempts,
                last_score=concept_mastery.last_score,
                repetition_number=getattr(concept_mastery, "repetition_number", 0) or 0,
                interval_days=getattr(concept_mastery, "interval_days", 1.0) or 1.0,
                easiness_factor=getattr(concept_mastery, "easiness_factor", 2.5) or 2.5,
                last_reviewed_at=last_rev,
                next_review_due_at=next_due,
                created_at=now,
                updated_at=now,
            )
            record.learner = learner
            self.session.add(record)

        else:
            record.mastery_score = concept_mastery.mastery_score
            record.mastery_level = concept_mastery.mastery_level.value
            record.confidence = concept_mastery.confidence
            record.attempts = concept_mastery.attempts
            record.correct_attempts = concept_mastery.correct_attempts
            record.partial_attempts = concept_mastery.partial_attempts
            record.incorrect_attempts = concept_mastery.incorrect_attempts
            record.last_score = concept_mastery.last_score
            if hasattr(concept_mastery, "repetition_number"):
                record.repetition_number = concept_mastery.repetition_number
            if hasattr(concept_mastery, "interval_days"):
                record.interval_days = concept_mastery.interval_days
            if hasattr(concept_mastery, "easiness_factor"):
                record.easiness_factor = concept_mastery.easiness_factor
            if last_rev is not None:
                record.last_reviewed_at = last_rev
            if next_due is not None:
                record.next_review_due_at = next_due
            record.updated_at = now

        await self.session.flush()

        # Recompute overall mastery for learner
        stmt_all = select(ConceptMasteryRecord.mastery_score).where(ConceptMasteryRecord.learner_id == learner.id)
        scores_res = await self.session.execute(stmt_all)
        all_scores = scores_res.scalars().all()
        if all_scores:
            learner.overall_mastery = round(sum(all_scores) / len(all_scores), 4)
        else:
            learner.overall_mastery = 0.0
        learner.updated_at = now
        await self.session.flush()
        return record

    async def record_lesson_completion(
        self,
        learner_id: str,
        lesson_id: str,
    ) -> Learner:
        """Record completed lesson uniquely."""
        clean_lesson_id = (lesson_id or "").strip()
        if not clean_lesson_id:
            raise InvalidProfileUpdateError("lesson_id cannot be empty or whitespace.")

        learner = await self.get_learner(learner_id)
        if learner is None:
            raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

        completed = list(learner.completed_lessons or [])
        if clean_lesson_id not in completed:
            completed.append(clean_lesson_id)
            learner.completed_lessons = completed
            learner.updated_at = utc_now()
            await self.session.flush()
        return learner

    async def record_assessment_score(
        self,
        learner_id: str,
        score: float,
    ) -> Learner:
        """Update assessment count and compute incremental running average."""
        if score is None or not (0.0 <= score <= 1.0):
            raise InvalidProfileUpdateError(f"Score must be between 0.0 and 1.0. Received: {score}")

        learner = await self.get_learner(learner_id)
        if learner is None:
            raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

        new_count = learner.assessment_count + 1
        new_avg = (learner.average_score * learner.assessment_count + score) / new_count
        learner.assessment_count = new_count
        learner.average_score = round(max(0.0, min(1.0, new_avg)), 4)
        learner.updated_at = utc_now()
        await self.session.flush()
        return learner

    async def log_learning_event(
        self,
        learner_id: str,
        event_type: str,
        session_id: Optional[str] = None,
        concept_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LearningEvent:
        """Append an event to the immutable learning event log."""
        event = LearningEvent(
            learner_id=learner_id,
            session_id=session_id,
            concept_id=concept_id,
            event_type=event_type,
            event_payload=payload or {},
            created_at=utc_now(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def create_session_log(
        self,
        session_id: str,
        learner_id: str,
        lesson_id: Optional[str] = None,
        topic: Optional[str] = None,
        material_id: Optional[str] = None,
        difficulty: str = "intermediate",
        language: str = "english",
        available_time_minutes: int = 20,
        desired_depth: str = "standard",
        session_metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionLog:
        """Initialize a new persistent session log."""
        now = utc_now()
        session_log = SessionLog(
            id=session_id,
            learner_id=learner_id,
            lesson_id=lesson_id,
            topic=topic,
            material_id=material_id,
            status="active",
            current_difficulty=difficulty,
            language=language,
            available_time_minutes=available_time_minutes,
            remaining_time_minutes=available_time_minutes,
            desired_depth=desired_depth,
            step_count=0,
            session_metadata=session_metadata or {},
            started_at=now,
        )
        self.session.add(session_log)
        await self.session.flush()
        return session_log

    async def update_session_log(
        self,
        session_id: str,
        status: Optional[str] = None,
        current_concept_id: Optional[str] = None,
        current_difficulty: Optional[str] = None,
        remaining_time_minutes: Optional[int] = None,
        step_increment: int = 0,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SessionLog]:
        """Update live status, concepts, and timer on a SessionLog."""
        stmt = select(SessionLog).where(SessionLog.id == session_id)
        res = await self.session.execute(stmt)
        sess = res.scalar_one_or_none()
        if sess is None:
            return None

        if status is not None:
            sess.status = status
            if status in ("completed", "abandoned"):
                sess.ended_at = utc_now()
        if current_concept_id is not None:
            sess.current_concept_id = current_concept_id
        if current_difficulty is not None:
            sess.current_difficulty = current_difficulty
        if remaining_time_minutes is not None:
            sess.remaining_time_minutes = max(0, remaining_time_minutes)
        if step_increment > 0:
            sess.step_count += step_increment
        if extra_metadata:
            meta = dict(sess.session_metadata or {})
            meta.update(extra_metadata)
            sess.session_metadata = meta

        await self.session.flush()
        return sess

    async def get_session_log(self, session_id: str) -> Optional[SessionLog]:
        """Fetch a SessionLog by its unique ID."""
        stmt = select(SessionLog).where(SessionLog.id == session_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_session_log(self, learner_id: str) -> Optional[SessionLog]:
        """Fetch the most recent active session for a learner."""
        stmt = (
            select(SessionLog)
            .where(SessionLog.learner_id == learner_id, SessionLog.status == "active")
            .order_by(desc(SessionLog.started_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_learner_sessions(
        self,
        learner_id: str,
        limit: int = 20,
    ) -> List[SessionLog]:
        """List historical and active sessions for a learner."""
        stmt = (
            select(SessionLog)
            .where(SessionLog.learner_id == learner_id)
            .order_by(desc(SessionLog.started_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def record_assessment_attempt(
        self,
        evaluation_id: str,
        learner_id: str,
        question_id: str,
        concept_id: str,
        question_type: str,
        student_answer: str,
        score: float,
        correctness: bool,
        confidence: float = 1.0,
        session_id: Optional[str] = None,
        concepts_demonstrated: Optional[List[str]] = None,
        concepts_missing: Optional[List[str]] = None,
        misconception_diagnosed: Optional[str] = None,
        severity: Optional[str] = None,
        evaluation_rubric: Optional[str] = None,
    ) -> AssessmentAttempt:
        """Persist a single question evaluation attempt."""
        attempt = AssessmentAttempt(
            id=evaluation_id,
            learner_id=learner_id,
            session_id=session_id,
            question_id=question_id,
            concept_id=concept_id,
            question_type=question_type,
            student_answer=student_answer,
            score=score,
            correctness=correctness,
            confidence=confidence,
            concepts_demonstrated=concepts_demonstrated or [],
            concepts_missing=concepts_missing or [],
            misconception_diagnosed=misconception_diagnosed,
            severity=severity,
            evaluation_rubric=evaluation_rubric,
            created_at=utc_now(),
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def get_learning_events(
        self,
        learner_id: str,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[LearningEvent]:
        """Fetch timeline of learning events for a learner."""
        stmt = select(LearningEvent).where(LearningEvent.learner_id == learner_id)
        if session_id is not None:
            stmt = stmt.where(LearningEvent.session_id == session_id)
        stmt = stmt.order_by(desc(LearningEvent.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_assessment_attempts(
        self,
        learner_id: str,
        concept_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AssessmentAttempt]:
        """Fetch historical assessment attempts for a learner."""
        stmt = select(AssessmentAttempt).where(AssessmentAttempt.learner_id == learner_id)
        if concept_id is not None:
            stmt = stmt.where(AssessmentAttempt.concept_id == concept_id)
        stmt = stmt.order_by(desc(AssessmentAttempt.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def to_learner_profile(self, learner: Learner) -> LearnerProfile:
        """Convert a persistent Learner ORM entity into the canonical LearnerProfile Pydantic schema."""
        pref = learner.preference
        lang = SupportedLanguage.ENGLISH
        diff = DifficultyLevel.INTERMEDIATE
        goal = None

        if pref:
            try:
                lang = SupportedLanguage(pref.preferred_language)
            except ValueError:
                lang = SupportedLanguage.ENGLISH
            try:
                diff = DifficultyLevel(pref.preferred_difficulty)
            except ValueError:
                diff = DifficultyLevel.INTERMEDIATE
            goal = pref.learning_goal

        # Reconstruct concept masteries
        masteries_dict: Dict[str, ConceptMastery] = {}
        strengths: List[str] = []
        weak_areas: List[str] = []
        mastered_concepts: List[str] = []
        active_concepts: List[str] = []

        for m in (learner.concept_masteries or []):
            try:
                m_level = MasteryLevel(m.mastery_level)
            except ValueError:
                m_level = MasteryLevel.NOT_STARTED

            c_mastery = ConceptMastery(
                concept_id=m.concept_id,
                mastery_score=m.mastery_score,
                mastery_level=m_level,
                confidence=m.confidence,
                attempts=m.attempts,
                correct_attempts=m.correct_attempts,
                partial_attempts=m.partial_attempts,
                incorrect_attempts=m.incorrect_attempts,
                last_score=m.last_score,
            )
            masteries_dict[m.concept_id] = c_mastery

            if m_level in (MasteryLevel.PROFICIENT, MasteryLevel.MASTERED):
                strengths.append(m.concept_id)
            if m_level in (MasteryLevel.NOT_STARTED, MasteryLevel.EMERGING):
                weak_areas.append(m.concept_id)
            if m_level == MasteryLevel.MASTERED:
                mastered_concepts.append(m.concept_id)
            if m_level in (MasteryLevel.EMERGING, MasteryLevel.DEVELOPING):
                active_concepts.append(m.concept_id)

        strengths.sort()
        weak_areas.sort()
        mastered_concepts.sort()
        active_concepts.sort()

        return LearnerProfile(
            learner_id=learner.id,
            name=learner.name,
            preferred_language=lang,
            learning_goal=goal,
            preferred_difficulty=diff,
            concept_masteries=masteries_dict,
            strengths=strengths,
            weak_areas=weak_areas,
            mastered_concepts=mastered_concepts,
            active_concepts=active_concepts,
            completed_lessons=list(learner.completed_lessons or []),
            total_lessons=learner.total_lessons,
            assessment_count=learner.assessment_count,
            average_score=learner.average_score,
            overall_mastery=learner.overall_mastery,
            created_at=learner.created_at,
            updated_at=learner.updated_at,
        )
