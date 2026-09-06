import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AIBrainException,
    InvalidSessionStateError,
    SessionNotFoundError,
    TeacherSessionError,
)
from app.core.gemini import gemini_client
from app.db.repository import LearnerRepository
from app.db.session import get_db_session
from app.schemas.adaptive import (
    AdaptationAction,
    AdaptationDecision,
    ConceptMastery,
)
from app.schemas.assessment import (
    EvaluationResult,
    MisconceptionAnalysis,
    Question,
    QuestionType,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel
from app.schemas.session import (
    AdvanceStepRequest,
    InstructionalDelivery,
    LessonSessionState,
    SessionStatus,
    SessionStepResponse,
    StartSessionRequest,
    SubmitAnswerRequest,
    TeachingStep,
)
from app.services.adaptive_engine import AdaptiveEngine, adaptive_engine
from app.services.answer_evaluator import answer_evaluator
from app.services.concept_service import concept_service
from app.services.mastery_engine import mastery_engine
from app.services.misconception_detector import misconception_detector
from app.services.question_generator import question_generator
from app.services.rag_service import RAGService, rag_service
from app.services.session_service import session_service
from app.services.teaching_content_engine import (
    TeachingContentEngine,
    teaching_content_engine,
)
from app.services.time_adaptive_planner import (
    TimeAdaptivePlanner,
    time_adaptive_planner,
)
from app.services.learning_memory_service import (
    LearningMemoryService,
    learning_memory_service,
)

logger = logging.getLogger(__name__)

# Maximum remediation attempts per concept before forcing advancement to prevent cognitive fatigue
MAX_REMEDIATION_ATTEMPTS = 2


class TeacherAgent:
    """Master pedagogical orchestrator implementing the continuous human-like teaching loop:
    Understand -> Plan -> Explain -> Demonstrate -> Question -> Evaluate -> Adapt -> Continue.
    """

    def __init__(
        self,
        gemini_client_instance=None,
        session_svc=None,
        question_gen=None,
        answer_eval=None,
        misc_det=None,
        mastery_eng=None,
        adapt_eng=None,
        concept_svc=None,
        content_eng=None,
        time_planner=None,
        rag_svc=None,
    ):
        self._gemini_client = gemini_client_instance or gemini_client
        self._session_service = session_svc or session_service
        self._question_generator = question_gen or question_generator
        self._answer_evaluator = answer_eval or answer_evaluator
        self._misconception_detector = misc_det or misconception_detector
        self._mastery_engine = mastery_eng or mastery_engine
        self._adaptive_engine = adapt_eng or adaptive_engine
        self._concept_service = concept_svc or concept_service
        self._content_engine = content_eng or TeachingContentEngine(client=self._gemini_client)
        self._time_planner = time_planner or time_adaptive_planner
        self._rag_service = rag_svc or rag_service
        self._learning_memory_service = learning_memory_service

    @property
    def active_sessions(self) -> Dict[str, LessonSessionState]:
        """In-memory active sessions dictionary managed by SessionService."""
        return self._session_service._cache

    async def get_or_restore_session(
        self,
        session_id: str,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Fetch active session from cache or reconstruct from persistent database storage."""
        return await self._session_service.get_session(session_id, db_session=db_session)

    async def get_active_session(
        self,
        session_id: str,
        db_session: Optional[AsyncSession] = None,
    ) -> LessonSessionState:
        """Fetch active session, ensuring it exists and is not already completed."""
        return await self._session_service.get_active_session(session_id, db_session=db_session)

    # --------------------------------------------------------------------
    # Loop Step 1 & 2: Understand & Plan -> Start Teaching Session
    # --------------------------------------------------------------------

    async def start_teaching_session(
        self,
        request: StartSessionRequest,
        db_session: Optional[AsyncSession] = None,
    ) -> SessionStepResponse:
        """Understand learner context, plan concept sequence, and deliver initial explanation."""
        if not request.learner_id or not request.learner_id.strip():
            raise TeacherSessionError("learner_id is required to start a teaching session.")

        learner_id = request.learner_id.strip()

        # Step 1: Understand Learner
        pref_lang = request.preferred_language or SupportedLanguage.ENGLISH
        pref_diff = request.preferred_difficulty or DifficultyLevel.INTERMEDIATE

        async def _check_profile(s: AsyncSession):
            repo = LearnerRepository(s)
            learner = await repo.get_learner(learner_id)
            if learner and learner.preference:
                nonlocal pref_lang, pref_diff
                if request.preferred_language is None:
                    try:
                        pref_lang = SupportedLanguage(learner.preference.preferred_language)
                    except ValueError:
                        pass
                if request.preferred_difficulty is None:
                    try:
                        pref_diff = DifficultyLevel(learner.preference.preferred_difficulty)
                    except ValueError:
                        pass

        try:
            if db_session is not None:
                await _check_profile(db_session)
            else:
                async with get_db_session() as s:
                    await _check_profile(s)
        except Exception as ex:
            logger.warning("Could not load learner profile for context: %s", ex)

        # Step 2: Plan Curriculum & Concept Sequence
        concept_ids: List[str] = []
        concept_names: Dict[str, str] = {}
        time_budget = max(1, request.available_time_minutes)

        if request.concept_ids:
            for cid in request.concept_ids:
                clean_cid = cid.strip()
                if clean_cid:
                    concept_ids.append(clean_cid)
                    concept_names[clean_cid] = clean_cid.replace("_", " ").title()

        elif request.topic and request.topic.strip():
            topic_clean = request.topic.strip()
            try:
                extracted = await self._concept_service.extract_concepts_from_topic(topic_clean)
                if extracted:
                    graph = self._concept_service.build_concept_graph(extracted)
                    prioritized = self._time_planner.prune_and_prioritize_concepts(
                        concept_graph=graph,
                        available_time_minutes=time_budget,
                        desired_depth=request.desired_depth,
                    )
                    for c in prioritized:
                        concept_ids.append(c.concept_id)
                        concept_names[c.concept_id] = c.name
            except Exception as ex:
                logger.warning("Dynamic concept extraction from topic failed, falling back: %s", ex)
                fallback_id = f"cpt_{hashlib.sha256(topic_clean.lower().encode()).hexdigest()[:12]}"
                concept_ids.append(fallback_id)
                concept_names[fallback_id] = topic_clean

        elif request.material_id:
            fallback_id = f"cpt_{hashlib.sha256(request.material_id.encode()).hexdigest()[:12]}"
            concept_ids.append(fallback_id)
            concept_names[fallback_id] = f"Material Module ({request.material_id[:8]})"

        if not concept_ids:
            # Fallback default concept if none specified
            default_id = "cpt_intro_core"
            concept_ids.append(default_id)
            concept_names[default_id] = "Foundational Overview"

        session_id = f"ses_{uuid.uuid4().hex[:16]}"
        time_budget = max(1, request.available_time_minutes)

        state = LessonSessionState(
            session_id=session_id,
            learner_id=learner_id,
            topic=request.topic,
            material_id=request.material_id,
            lesson_id=request.lesson_id,
            concepts=concept_ids,
            concept_names=concept_names,
            current_concept_index=0,
            current_step=TeachingStep.EXPLAIN,
            status=SessionStatus.ACTIVE,
            difficulty=pref_diff,
            language=pref_lang,
            time_budget_minutes=time_budget,
            remaining_time_minutes=time_budget,
            desired_depth=request.desired_depth,
            step_count=1,
            remediation_attempts={},
            completed_concepts=[],
        )

        # Step 3: Deliver initial EXPLAIN
        initial_delivery = await self._generate_delivery(
            concept_id=state.current_concept_id or concept_ids[0],
            concept_name=state.current_concept_name or "Core Concept",
            step=TeachingStep.EXPLAIN,
            difficulty=state.difficulty,
            language=state.language,
            depth=state.desired_depth,
            material_id=state.material_id,
        )
        state.current_delivery = initial_delivery

        # Save session to persistent store
        await self._session_service.create_session(state, db_session=db_session)

        return SessionStepResponse(
            session_id=state.session_id,
            learner_id=state.learner_id,
            current_step=state.current_step,
            status=state.status,
            current_concept_id=state.current_concept_id,
            current_concept_name=state.current_concept_name,
            concept_index=state.current_concept_index,
            total_concepts=len(state.concepts),
            difficulty=state.difficulty,
            language=state.language,
            remaining_time_minutes=state.remaining_time_minutes,
            step_count=state.step_count,
            delivery=state.current_delivery,
            message="Welcome! Here is your concept explanation. Review the intuition and click 'Next' to see a demonstration.",
        )

    # --------------------------------------------------------------------
    # Loop Step 3 & 4: Advance Step (Explain -> Demonstrate -> Question)
    # --------------------------------------------------------------------

    async def advance_step(
        self,
        request: AdvanceStepRequest,
        db_session: Optional[AsyncSession] = None,
    ) -> SessionStepResponse:
        """Advance the teaching loop to the next instructional phase."""
        state = await self._session_service.get_session(request.session_id, db_session=db_session)

        if state.is_completed:
            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=TeachingStep.COMPLETE,
                status=SessionStatus.COMPLETED,
                current_concept_id=state.current_concept_id,
                current_concept_name=state.current_concept_name,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                step_count=state.step_count,
                message="This session has concluded. Great job!",
            )

        cid = state.current_concept_id or (state.concepts[0] if state.concepts else "concept_core")
        cname = state.current_concept_name or "Core Concept"

        # Advance state
        if state.current_step == TeachingStep.EXPLAIN:
            # Advance to DEMONSTRATE
            state.current_step = TeachingStep.DEMONSTRATE
            state.step_count += 1
            state.remaining_time_minutes = max(0, state.remaining_time_minutes - 2)

            delivery = await self._generate_delivery(
                concept_id=cid,
                concept_name=cname,
                step=TeachingStep.DEMONSTRATE,
                difficulty=state.difficulty,
                language=state.language,
                depth=state.desired_depth,
                material_id=state.material_id,
            )
            state.current_delivery = delivery
            await self._session_service.save_session(state, db_session=db_session)

            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=state.current_step,
                status=state.status,
                current_concept_id=cid,
                current_concept_name=cname,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                step_count=state.step_count,
                delivery=delivery,
                message="Here is a concrete demonstration and applied example. Click 'Next' when ready for a check question!",
            )

        elif state.current_step == TeachingStep.DEMONSTRATE:
            # Advance to QUESTION
            state.current_step = TeachingStep.QUESTION
            state.step_count += 1
            state.remaining_time_minutes = max(0, state.remaining_time_minutes - 2)

            question = await self._generate_concept_question(
                concept_id=cid,
                concept_name=cname,
                difficulty=state.difficulty,
                language=state.language,
                lesson_id=state.lesson_id,
            )
            state.last_question = question
            await self._session_service.save_session(state, db_session=db_session)

            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=state.current_step,
                status=state.status,
                current_concept_id=cid,
                current_concept_name=cname,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                step_count=state.step_count,
                question=question,
                message="Let's check your understanding. Please answer the question below.",
            )

        elif state.current_step == TeachingStep.QUESTION:
            # Already waiting on question answer
            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=state.current_step,
                status=state.status,
                current_concept_id=cid,
                current_concept_name=cname,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                step_count=state.step_count,
                question=state.last_question,
                message="Please submit your response to the current question to continue.",
            )

        elif state.current_step == TeachingStep.ADAPT:
            # Proceed after adaptation
            state.current_step = TeachingStep.EXPLAIN
            state.step_count += 1
            delivery = await self._generate_delivery(
                concept_id=cid,
                concept_name=cname,
                step=TeachingStep.EXPLAIN,
                difficulty=state.difficulty,
                language=state.language,
                depth=state.desired_depth,
                material_id=state.material_id,
            )
            state.current_delivery = delivery
            await self._session_service.save_session(state, db_session=db_session)

            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=state.current_step,
                status=state.status,
                current_concept_id=cid,
                current_concept_name=cname,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                step_count=state.step_count,
                delivery=delivery,
                message="Continuing instruction based on adaptive recommendations.",
            )

        else:
            raise InvalidSessionStateError(f"Cannot advance step from '{state.current_step}'.")

    # --------------------------------------------------------------------
    # Loop Step 5, 6, 7 & 8: Question Answered -> Evaluate -> Adapt -> Continue
    # --------------------------------------------------------------------

    async def submit_learner_answer(
        self,
        request: SubmitAnswerRequest,
        db_session: Optional[AsyncSession] = None,
    ) -> SessionStepResponse:
        """Evaluate answer, detect misconceptions, update mastery, adapt curriculum, and continue."""
        state = await self._session_service.get_session(request.session_id, db_session=db_session)

        if state.is_completed:
            return SessionStepResponse(
                session_id=state.session_id,
                learner_id=state.learner_id,
                current_step=TeachingStep.COMPLETE,
                status=SessionStatus.COMPLETED,
                current_concept_id=state.current_concept_id,
                current_concept_name=state.current_concept_name,
                concept_index=state.current_concept_index,
                total_concepts=len(state.concepts),
                difficulty=state.difficulty,
                language=state.language,
                remaining_time_minutes=state.remaining_time_minutes,
                message="Session is already completed.",
            )

        if not state.last_question or state.last_question.question_id != request.question_id:
            raise TeacherSessionError("Submitted answer does not match the active session question.")

        question = state.last_question
        cid = question.concept_id or (state.current_concept_id or "concept_core")
        cname = state.current_concept_name or "Core Concept"

        student_answer = StudentAnswer(
            question_id=question.question_id,
            answer_text=request.answer_text,
            selected_option=request.selected_option,
            reasoning=request.reasoning,
        )
        state.last_student_answer = student_answer

        # Step 6: Evaluate Answer
        eval_result = await self._answer_evaluator.evaluate_answer(
            question=question,
            student_answer=student_answer,
        )
        state.last_evaluation = eval_result

        # Step 7: Detect Misconceptions
        concept_obj = Concept(
            concept_id=cid,
            name=cname,
            description=f"Concept: {cname}",
            difficulty=state.difficulty,
            learning_objectives=[question.learning_objective],
        )
        misc_analysis = await self._misconception_detector.detect_misconceptions(
            question=question,
            student_answer=student_answer,
            evaluation_result=eval_result,
            concept=concept_obj,
        )
        state.last_misconception_analysis = misc_analysis

        # Update concept mastery via mastery engine
        # Look up previous mastery if exists
        prev_mastery = None
        async def _get_prev_mastery(s: AsyncSession):
            nonlocal prev_mastery
            repo = LearnerRepository(s)
            learner = await repo.get_learner(state.learner_id)
            if learner:
                for m in learner.concept_masteries:
                    if m.concept_id == cid:
                        from app.schemas.adaptive import MasteryLevel
                        prev_mastery = ConceptMastery(
                            concept_id=cid,
                            mastery_score=m.mastery_score,
                            mastery_level=MasteryLevel(m.mastery_level),
                            confidence=m.confidence,
                            attempts=m.attempts,
                            correct_attempts=m.correct_attempts,
                            partial_attempts=m.partial_attempts,
                            incorrect_attempts=m.incorrect_attempts,
                            last_score=m.last_score,
                            repetition_number=getattr(m, "repetition_number", 0) or 0,
                            interval_days=getattr(m, "interval_days", 1.0) or 1.0,
                            easiness_factor=getattr(m, "easiness_factor", 2.5) or 2.5,
                        )
                        break

        try:
            if db_session is not None:
                await _get_prev_mastery(db_session)
            else:
                async with get_db_session() as s:
                    await _get_prev_mastery(s)
        except Exception as ex:
            logger.warning("Could not read previous mastery: %s", ex)
            if db_session is not None:
                try:
                    await db_session.rollback()
                except Exception:
                    pass

        updated_mastery = self._mastery_engine.update_mastery(
            concept_id=cid,
            evaluation_result=eval_result,
            previous_mastery=prev_mastery,
        )

        # Compute SM-2 spaced repetition decay curve and review parameters
        old_rep = getattr(prev_mastery, "repetition_number", 0) if prev_mastery else 0
        old_interval = getattr(prev_mastery, "interval_days", 1.0) if prev_mastery else 1.0
        old_ef = getattr(prev_mastery, "easiness_factor", 2.5) if prev_mastery else 2.5

        new_rep, new_interval, new_ef = LearningMemoryService.calculate_sm2_update(
            score=eval_result.score,
            current_repetition=old_rep,
            current_interval_days=old_interval,
            current_easiness_factor=old_ef,
        )
        now_dt = datetime.now(timezone.utc)
        updated_mastery.repetition_number = new_rep
        updated_mastery.interval_days = new_interval
        updated_mastery.easiness_factor = new_ef
        updated_mastery.last_reviewed_at = now_dt.isoformat()
        updated_mastery.next_review_due_at = (now_dt + timedelta(days=new_interval)).isoformat()
        updated_mastery.retention_probability = 1.0

        # Step 8: Adaptive Engine Decision (Canonical: decide_next_action)
        adaptive_fn = getattr(self._adaptive_engine, "decide_next_action", None) or getattr(self._adaptive_engine, "determine_adaptation")

        decision = adaptive_fn(
            current_concept_id=cid,
            current_difficulty=state.difficulty,
            evaluation_result=eval_result,
            concept_mastery=updated_mastery,
            misconception_analysis=misc_analysis,
            learner_id=state.learner_id,
            session_id=state.session_id,
        )
        state.last_adaptation = decision

        # Persist assessment attempt, mastery, and events to SQLite
        async def _persist_eval(s: AsyncSession):
            repo = LearnerRepository(s)
            await repo.upsert_concept_mastery(state.learner_id, updated_mastery)
            await repo.record_assessment_score(state.learner_id, eval_result.score)
            
            top_misc = misc_analysis.misconceptions[0] if (misc_analysis and misc_analysis.misconceptions) else None
            await repo.record_assessment_attempt(
                evaluation_id=eval_result.evaluation_id,
                learner_id=state.learner_id,
                session_id=state.session_id,
                question_id=question.question_id,
                concept_id=cid,
                question_type=question.question_type.value,
                student_answer=student_answer.answer_text or student_answer.selected_option or "",
                score=eval_result.score,
                correctness=eval_result.correctness,
                confidence=eval_result.confidence,
                concepts_demonstrated=eval_result.concepts_demonstrated,
                concepts_missing=eval_result.concepts_missing,
                misconception_diagnosed=top_misc.description if top_misc else None,
                severity=top_misc.severity.value if top_misc else None,
                evaluation_rubric=question.evaluation_rubric,
            )
            await repo.log_learning_event(
                learner_id=state.learner_id,
                session_id=state.session_id,
                concept_id=cid,
                event_type="ANSWER_EVALUATED",
                payload={
                    "score": eval_result.score,
                    "action": decision.action.value,
                    "reason": decision.reason,
                },
            )
            await repo.log_learning_event(
                learner_id=state.learner_id,
                session_id=state.session_id,
                concept_id=cid,
                event_type="MEMORY_UPDATED",
                payload={
                    "score": eval_result.score,
                    "repetition": new_rep,
                    "interval_days": new_interval,
                    "easiness_factor": new_ef,
                },
            )

        try:
            if db_session is not None:
                await _persist_eval(db_session)
            else:
                async with get_db_session() as s:
                    await _persist_eval(s)
        except Exception as ex:
            logger.error("Failed to persist assessment attempt or mastery: %s", ex)
            if db_session is not None:
                try:
                    await db_session.rollback()
                except Exception:
                    pass

        # ----------------------------------------------------------------
        # Execute Adaptation Action
        # ----------------------------------------------------------------
        act = decision.action
        next_message = f"Evaluation: Score {int(eval_result.score * 100)}%. "
        state.remaining_time_minutes = max(0, state.remaining_time_minutes - 2)

        if act == AdaptationAction.ADVANCE_CONCEPT or act == AdaptationAction.CONTINUE:
            if cid not in state.completed_concepts:
                state.completed_concepts.append(cid)
            state.remediation_attempts[cid] = 0

            # Move to next concept
            state.current_concept_index += 1
            if state.current_concept_index >= len(state.concepts):
                # All concepts finished!
                state.status = SessionStatus.COMPLETED
                state.current_step = TeachingStep.COMPLETE
                next_message += "Congratulations! You have mastered all concepts in this session."
                await self._session_service.end_session(state.session_id, SessionStatus.COMPLETED, db_session=db_session)
            else:
                state.current_step = TeachingStep.EXPLAIN
                state.difficulty = decision.target_difficulty
                new_cid = state.current_concept_id
                new_cname = state.current_concept_name or "Next Concept"
                state.current_delivery = await self._generate_delivery(
                    concept_id=new_cid,
                    concept_name=new_cname,
                    step=TeachingStep.EXPLAIN,
                    difficulty=state.difficulty,
                    language=state.language,
                    depth=state.desired_depth,
                    material_id=state.material_id,
                )
                next_message += f"Moving forward to next concept: '{new_cname}'."

        elif act in (AdaptationAction.RETEACH_CONCEPT, AdaptationAction.REMEDIATE_MISCONCEPTION):
            attempts = state.remediation_attempts.get(cid, 0) + 1
            state.remediation_attempts[cid] = attempts

            if attempts > MAX_REMEDIATION_ATTEMPTS:
                # Anti-loop guard: Don't frustrate learner infinitely
                logger.info("Remediation limit reached for concept '%s', advancing forward", cid)
                if cid not in state.completed_concepts:
                    state.completed_concepts.append(cid)
                state.current_concept_index += 1
                if state.current_concept_index >= len(state.concepts):
                    state.status = SessionStatus.COMPLETED
                    state.current_step = TeachingStep.COMPLETE
                    next_message += "We've reached our time limit for this concept. Session completed!"
                    await self._session_service.end_session(state.session_id, SessionStatus.COMPLETED, db_session=db_session)
                else:
                    state.current_step = TeachingStep.EXPLAIN
                    new_cid = state.current_concept_id
                    new_cname = state.current_concept_name or "Next Concept"
                    state.current_delivery = await self._generate_delivery(
                        concept_id=new_cid,
                        concept_name=new_cname,
                        step=TeachingStep.EXPLAIN,
                        difficulty=state.difficulty,
                        language=state.language,
                        depth=state.desired_depth,
                        material_id=state.material_id,
                    )
                    next_message += f"We've spent extra time here. Let's move ahead to '{new_cname}' and revisit later."
            else:
                # Deliver targeted remediation explanation
                state.current_step = TeachingStep.EXPLAIN
                misc_desc = misc_analysis.misconceptions[0].description if (misc_analysis and misc_analysis.misconceptions) else None
                state.current_delivery = await self._generate_delivery(
                    concept_id=cid,
                    concept_name=cname,
                    step=TeachingStep.EXPLAIN,
                    difficulty=decision.target_difficulty,
                    language=state.language,
                    depth=state.desired_depth,
                    remediation_notes=misc_desc or decision.reason,
                    material_id=state.material_id,
                )
                next_message += f"Let's review this concept together to address: {decision.reason}."

        elif act == AdaptationAction.RETRY_QUESTION:
            state.current_step = TeachingStep.QUESTION
            state.difficulty = decision.target_difficulty
            question = await self._generate_concept_question(
                concept_id=cid,
                concept_name=cname,
                difficulty=state.difficulty,
                language=state.language,
                lesson_id=state.lesson_id,
            )
            state.last_question = question
            next_message += "Almost there! Let's try another question to reinforce this point."

        elif act in (AdaptationAction.INCREASE_DIFFICULTY, AdaptationAction.DECREASE_DIFFICULTY):
            state.difficulty = decision.target_difficulty
            state.current_step = TeachingStep.EXPLAIN
            state.current_delivery = await self._generate_delivery(
                concept_id=cid,
                concept_name=cname,
                step=TeachingStep.EXPLAIN,
                difficulty=state.difficulty,
                language=state.language,
                depth=state.desired_depth,
                material_id=state.material_id,
            )
            next_message += f"Adjusted difficulty to {state.difficulty.value}. Continuing instruction."

        elif act == AdaptationAction.REVIEW_PREREQUISITE:
            target_prereq = decision.target_concept_id
            if target_prereq not in state.concepts:
                # Insert prerequisite before current index
                state.concepts.insert(state.current_concept_index, target_prereq)
                state.concept_names[target_prereq] = target_prereq.replace("_", " ").title()

            state.current_step = TeachingStep.EXPLAIN
            prereq_name = state.concept_names.get(target_prereq, target_prereq)
            state.current_delivery = await self._generate_delivery(
                concept_id=target_prereq,
                concept_name=prereq_name,
                step=TeachingStep.EXPLAIN,
                difficulty=decision.target_difficulty,
                language=state.language,
                depth=state.desired_depth,
                remediation_notes=f"Reviewing foundation for {cname}",
                material_id=state.material_id,
            )
            next_message += f"Let's briefly review the prerequisite: '{prereq_name}'."

        # Save final state
        await self._session_service.save_session(state, db_session=db_session)

        return SessionStepResponse(
            session_id=state.session_id,
            learner_id=state.learner_id,
            current_step=state.current_step,
            status=state.status,
            current_concept_id=state.current_concept_id,
            current_concept_name=state.current_concept_name,
            concept_index=state.current_concept_index,
            total_concepts=len(state.concepts),
            difficulty=state.difficulty,
            language=state.language,
            remaining_time_minutes=state.remaining_time_minutes,
            step_count=state.step_count,
            delivery=state.current_delivery,
            question=state.last_question if state.current_step == TeachingStep.QUESTION else None,
            evaluation=eval_result,
            misconception_analysis=misc_analysis,
            adaptation=decision,
            message=next_message,
        )

    # --------------------------------------------------------------------
    # Multilingual Language Switching
    # --------------------------------------------------------------------

    async def switch_session_language(
        self,
        session_id: str,
        new_language: SupportedLanguage,
        db_session: Optional[AsyncSession] = None,
    ) -> SessionStepResponse:
        """Switch instructional language mid-session, update profile preference, and re-render delivery."""
        state = await self._session_service.get_session(session_id, db_session=db_session)
        old_lang = state.language
        state.language = new_language

        cid = state.current_concept_id or (state.concepts[0] if state.concepts else "cpt_core")
        cname = state.current_concept_name or "Core Concept"

        # If on explain or demonstrate, re-render content in the new language immediately
        if state.current_step in (TeachingStep.EXPLAIN, TeachingStep.DEMONSTRATE):
            state.current_delivery = await self._generate_delivery(
                concept_id=cid,
                concept_name=cname,
                step=state.current_step,
                difficulty=state.difficulty,
                language=new_language,
                depth=state.desired_depth,
                material_id=state.material_id,
            )

        # Update persistent learner preferences and log event in DB
        async def _update_db_pref(s: AsyncSession):
            repo = LearnerRepository(s)
            try:
                await repo.update_preferences(
                    learner_id=state.learner_id,
                    preferred_language=new_language.value,
                )
            except Exception as ex:
                logger.warning("Could not update learner preferred language in DB: %s", ex)

            await repo.log_learning_event(
                learner_id=state.learner_id,
                session_id=state.session_id,
                concept_id=cid,
                event_type="LANGUAGE_CHANGED",
                payload={"old_language": old_lang.value, "new_language": new_language.value},
            )

        try:
            if db_session is not None:
                await _update_db_pref(db_session)
            else:
                async with get_db_session() as s:
                    await _update_db_pref(s)
        except Exception as ex:
            logger.error("Failed to update language preferences: %s", ex)

        await self._session_service.save_session(state, db_session=db_session)

        lang_label = "Hindi" if new_language == SupportedLanguage.HINDI else ("Hinglish" if new_language == SupportedLanguage.HINGLISH else "English")
        return SessionStepResponse(
            session_id=state.session_id,
            learner_id=state.learner_id,
            current_step=state.current_step,
            status=state.status,
            current_concept_id=cid,
            current_concept_name=cname,
            concept_index=state.current_concept_index,
            total_concepts=len(state.concepts),
            difficulty=state.difficulty,
            language=state.language,
            remaining_time_minutes=state.remaining_time_minutes,
            step_count=state.step_count,
            delivery=state.current_delivery,
            question=state.last_question if state.current_step == TeachingStep.QUESTION else None,
            evaluation=state.last_evaluation,
            misconception_analysis=state.last_misconception_analysis,
            adaptation=state.last_adaptation,
            message=f"Language switched to {lang_label}. Delivery updated.",
        )

    # --------------------------------------------------------------------
    # Pedagogical Content Generation Helpers
    # --------------------------------------------------------------------

    async def _generate_delivery(
        self,
        concept_id: str,
        concept_name: str,
        step: TeachingStep,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        depth: str = "standard",
        remediation_notes: Optional[str] = None,
        material_id: Optional[str] = None,
    ) -> InstructionalDelivery:
        """Generate structured pedagogical explanation or demonstration via TeachingContentEngine."""
        source_chunks = None
        if material_id and material_id.strip():
            try:
                # Query RAG service for relevant chunks grounded in current concept and material_id
                chunks = await self._rag_service.search(
                    query=concept_name,
                    top_k=3,
                    material_id=material_id.strip(),
                )
                if chunks:
                    source_chunks = chunks
            except Exception as ex:
                logger.warning(
                    "RAG retrieval failed for concept '%s' in material '%s': %s",
                    concept_name,
                    material_id,
                    ex,
                )

        if remediation_notes:
            return await self._content_engine.generate_remediation(
                concept=concept_name,
                misconception=remediation_notes,
                difficulty=difficulty,
                language=language,
                depth=depth,
                concept_id=concept_id,
                source_chunks=source_chunks,
            )
        elif step == TeachingStep.EXPLAIN:
            return await self._content_engine.generate_explanation(
                concept=concept_name,
                difficulty=difficulty,
                language=language,
                depth=depth,
                concept_id=concept_id,
                source_chunks=source_chunks,
            )
        else:
            return await self._content_engine.generate_demonstration(
                concept=concept_name,
                difficulty=difficulty,
                language=language,
                depth=depth,
                concept_id=concept_id,
                source_chunks=source_chunks,
            )

    async def _generate_concept_question(
        self,
        concept_id: str,
        concept_name: str,
        difficulty: DifficultyLevel,
        language: SupportedLanguage,
        lesson_id: Optional[str] = None,
    ) -> Question:
        """Generate a validated pedagogical question assessing the current concept."""
        concept_obj = Concept(
            concept_id=concept_id,
            name=concept_name,
            description=f"Assessment of {concept_name}",
            difficulty=difficulty,
            learning_objectives=[f"Explain and apply key principles of {concept_name}"],
        )

        try:
            return await self._question_generator.generate_question(
                concept=concept_obj,
                question_type=QuestionType.CONCEPTUAL,
                learning_objective=f"Assess core understanding of {concept_name}",
                lesson_id=lesson_id,
            )
        except Exception as ex:
            logger.warning("Question generation failed, using fallback diagnostic question: %s", ex)
            if language == SupportedLanguage.HINDI:
                q_text = f"{concept_name} के मूलभूत सिद्धांत और महत्व को समझाइए।"
                ans_text = f"{concept_name} एक महत्वपूर्ण घटक है जो व्यवस्थित संचालन प्रदान करता है।"
                exp_text = f"{concept_name} को समझना बुनियादी दक्षता के लिए आवश्यक है।"
            elif language == SupportedLanguage.HINGLISH:
                q_text = f"{concept_name} ka fundamental mechanism aur importance explain kijiye."
                ans_text = f"{concept_name} ek essential building block hai jo system me systematic operation provide karta hai."
                exp_text = f"{concept_name} ko samajhna foundational mastery ke liye zaroori hai."
            else:
                q_text = f"Explain the fundamental mechanism and importance of {concept_name}."
                ans_text = f"{concept_name} serves as a key building block providing systematic operation and structure."
                exp_text = f"Understanding {concept_name} is essential for foundational mastery."

            q_id = f"qst_{hashlib.sha256(f'{concept_id}:{q_text}'.encode()).hexdigest()[:16]}"
            return Question(
                question_id=q_id,
                question_type=QuestionType.CONCEPTUAL,
                question_text=q_text,
                concept_id=concept_id,
                lesson_id=lesson_id,
                difficulty=difficulty,
                learning_objective=f"Understand {concept_name}",
                options=[],
                correct_answer=ans_text,
                explanation=exp_text,
            )

    # Convenience alias
    submit_answer = submit_learner_answer


teacher_agent = TeacherAgent()


