from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidSessionStateError, TeacherSessionError
from app.db.models import SessionLog
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.adaptive import AdaptationAction, AdaptationDecision, ConceptMastery, MasteryLevel
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.schemas.session import (
    AdvanceStepRequest,
    InstructionalDelivery,
    LessonSessionState,
    SessionStatus,
    StartSessionRequest,
    SubmitAnswerRequest,
    TeachingStep,
)
from app.services.session_service import SessionService
from app.services.teacher_agent import TeacherAgent


@pytest_asyncio.fixture
async def async_db_session():
    """Isolated in-memory SQLite database session for unit testing teacher agent."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Pre-seed a test learner
        repo = LearnerRepository(session)
        await repo.create_learner(
            learner_id="test_learner_01",
            name="Euler",
            preferred_language="english",
            preferred_difficulty="intermediate",
        )
        yield session

    await engine.dispose()


@pytest.fixture
def mock_agent_components():
    """Create a suite of mock services for deterministic testing of the TeacherAgent loop."""
    mock_gemini = MagicMock()
    mock_session_svc = SessionService()

    mock_q_gen = MagicMock()
    mock_q_gen.generate_question = AsyncMock(return_value=Question(
        question_id="qst_mock_001",
        question_type=QuestionType.CONCEPTUAL,
        question_text="What is a hash collision and how is it resolved?",
        concept_id="cpt_hash_tables",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Explain collision resolution",
        correct_answer="A collision occurs when two keys produce the same hash index. Resolved via chaining or open addressing.",
        explanation="Chaining uses linked lists while open addressing probes subsequent buckets.",
    ))

    mock_ans_eval = MagicMock()
    mock_misc_det = MagicMock()
    mock_mastery = MagicMock()
    mock_adapt = MagicMock()
    mock_adapt.decide_next_action = mock_adapt.determine_adaptation
    mock_concept_svc = MagicMock()

    agent = TeacherAgent(
        gemini_client_instance=mock_gemini,
        session_svc=mock_session_svc,
        question_gen=mock_q_gen,
        answer_eval=mock_ans_eval,
        misc_det=mock_misc_det,
        mastery_eng=mock_mastery,
        adapt_eng=mock_adapt,
        concept_svc=mock_concept_svc,
    )

    return {
        "agent": agent,
        "session_svc": mock_session_svc,
        "q_gen": mock_q_gen,
        "ans_eval": mock_ans_eval,
        "misc_det": mock_misc_det,
        "mastery": mock_mastery,
        "adapt": mock_adapt,
    }


# ====================================================================
# Phase 2 Unit Tests
# ====================================================================

@pytest.mark.asyncio
async def test_01_start_session_creation(async_db_session, mock_agent_components):
    """Verify start_teaching_session initializes state, saves to DB, and delivers initial explanation."""
    agent = mock_agent_components["agent"]

    req = StartSessionRequest(
        learner_id="test_learner_01",
        topic="Hash Tables",
        concept_ids=["cpt_hash_functions", "cpt_collision_resolution"],
        available_time_minutes=20,
        desired_depth="standard",
    )

    resp = await agent.start_teaching_session(req, db_session=async_db_session)

    assert resp.session_id.startswith("ses_")
    assert resp.learner_id == "test_learner_01"
    assert resp.current_step == TeachingStep.EXPLAIN
    assert resp.status == SessionStatus.ACTIVE
    assert resp.current_concept_id == "cpt_hash_functions"
    assert resp.total_concepts == 2
    assert resp.delivery is not None
    assert resp.delivery.step == TeachingStep.EXPLAIN

    # Verify persistent DB record
    repo = LearnerRepository(async_db_session)
    sess_log = await repo.get_session_log(resp.session_id)
    assert sess_log is not None
    assert sess_log.learner_id == "test_learner_01"
    assert sess_log.status == "active"
    assert sess_log.available_time_minutes == 20


@pytest.mark.asyncio
async def test_02_advance_step_explain_to_demonstrate(async_db_session, mock_agent_components):
    """Verify advancing from EXPLAIN transitions to DEMONSTRATE with practical example content."""
    agent = mock_agent_components["agent"]

    req = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_sorting"],
        available_time_minutes=15,
    )
    start_resp = await agent.start_teaching_session(req, db_session=async_db_session)
    assert start_resp.current_step == TeachingStep.EXPLAIN

    # Advance to DEMONSTRATE
    adv_req = AdvanceStepRequest(session_id=start_resp.session_id, learner_id="test_learner_01")
    adv_resp = await agent.advance_step(adv_req, db_session=async_db_session)

    assert adv_resp.current_step == TeachingStep.DEMONSTRATE
    assert adv_resp.delivery is not None
    assert adv_resp.delivery.step == TeachingStep.DEMONSTRATE
    assert adv_resp.remaining_time_minutes < 15
    assert adv_resp.step_count == 2


@pytest.mark.asyncio
async def test_03_advance_step_demonstrate_to_question(async_db_session, mock_agent_components):
    """Verify advancing from DEMONSTRATE transitions to QUESTION and attaches diagnostic question."""
    agent = mock_agent_components["agent"]

    req = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_hash_tables"],
        available_time_minutes=20,
    )
    start_resp = await agent.start_teaching_session(req, db_session=async_db_session)

    adv_req = AdvanceStepRequest(session_id=start_resp.session_id, learner_id="test_learner_01")
    # Step 1 -> DEMONSTRATE
    await agent.advance_step(adv_req, db_session=async_db_session)
    # Step 2 -> QUESTION
    q_resp = await agent.advance_step(adv_req, db_session=async_db_session)

    assert q_resp.current_step == TeachingStep.QUESTION
    assert q_resp.question is not None
    assert q_resp.question.question_id == "qst_mock_001"
    assert q_resp.question.concept_id == "cpt_hash_tables"


@pytest.mark.asyncio
async def test_04_submit_answer_correct_advances_concept(async_db_session, mock_agent_components):
    """Verify submitting a correct answer increases mastery and advances to the next concept."""
    agent = mock_agent_components["agent"]
    mocks = mock_agent_components

    # Configure mock responses for a correct answer
    mocks["ans_eval"].evaluate_answer = AsyncMock(return_value=EvaluationResult(
        evaluation_id="eval_001",
        question_id="qst_mock_001",
        concept_id="cpt_c1",
        correctness=True,
        score=0.95,
        confidence=1.0,
        expected_answer="Correct Answer",
        student_answer="My correct answer",
        concepts_demonstrated=["cpt_c1"],
        concepts_missing=[],
        evidence="Student precisely explained collision resolution techniques.",
        feedback="Excellent job explaining chaining and open addressing!",
    ))
    mocks["misc_det"].detect_misconceptions = AsyncMock(return_value=MisconceptionAnalysis(
        detected=False,
        misconceptions=[],
        overall_confidence=1.0,
        summary="No misconceptions.",
    ))
    mocks["mastery"].update_mastery = MagicMock(return_value=ConceptMastery(
        concept_id="cpt_c1",
        mastery_score=0.95,
        mastery_level=MasteryLevel.MASTERED,
        attempts=1,
        correct_attempts=1,
    ))
    mocks["adapt"].decide_next_action = MagicMock(return_value=AdaptationDecision(
        decision_id="adt_001",
        current_concept_id="cpt_c1",
        action=AdaptationAction.ADVANCE_CONCEPT,
        target_concept_id="cpt_c2",
        target_difficulty=DifficultyLevel.INTERMEDIATE,
        reason="Mastered concept with 95% score.",
        mastery_score=0.95,
    ))
    mocks["adapt"].determine_adaptation = mocks["adapt"].decide_next_action

    # Start session with 2 concepts
    req = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_c1", "cpt_c2"],
        available_time_minutes=20,
    )
    start_resp = await agent.start_teaching_session(req, db_session=async_db_session)
    sid = start_resp.session_id

    # Advance to question
    adv_req = AdvanceStepRequest(session_id=sid, learner_id="test_learner_01")
    await agent.advance_step(adv_req, db_session=async_db_session)
    q_resp = await agent.advance_step(adv_req, db_session=async_db_session)

    # Submit answer
    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="test_learner_01",
        question_id=q_resp.question.question_id,
        answer_text="Chaining with linked lists or open addressing probing.",
    )
    ans_resp = await agent.submit_learner_answer(sub_req, db_session=async_db_session)

    assert ans_resp.evaluation is not None
    assert ans_resp.evaluation.score == 0.95
    assert ans_resp.adaptation.action == AdaptationAction.ADVANCE_CONCEPT
    assert ans_resp.current_concept_id == "cpt_c2"
    assert ans_resp.concept_index == 1
    assert ans_resp.current_step == TeachingStep.EXPLAIN


@pytest.mark.asyncio
async def test_05_submit_answer_misconception_reteaches(async_db_session, mock_agent_components):
    """Verify submitting an answer with misconceptions triggers reteaching and stays on concept."""
    agent = mock_agent_components["agent"]
    mocks = mock_agent_components

    mocks["ans_eval"].evaluate_answer = AsyncMock(return_value=EvaluationResult(
        evaluation_id="eval_002",
        question_id="qst_mock_001",
        concept_id="cpt_c1",
        correctness=False,
        score=0.30,
        confidence=0.9,
        expected_answer="Collision resolution via chaining or probing.",
        student_answer="Hashing always guarantees unique slots.",
        concepts_demonstrated=[],
        concepts_missing=["cpt_c1"],
        evidence="Student incorrectly claimed collisions cannot occur.",
        feedback="Recall the pigeonhole principle: collisions are mathematically inevitable.",
    ))
    mocks["misc_det"].detect_misconceptions = AsyncMock(return_value=MisconceptionAnalysis(
        detected=True,
        misconceptions=[
            Misconception(
                misconception_id="msc_001",
                concept_id="cpt_c1",
                source_question_id="qst_mock_001",
                description="Believes hash functions never have collisions",
                evidence="Student claimed unique slots guaranteed",
                severity=MisconceptionSeverity.HIGH,
                confidence=0.9,
            )
        ],
        overall_confidence=0.9,
        summary="Misconception on pigeonhole principle.",
    ))
    mocks["mastery"].update_mastery = MagicMock(return_value=ConceptMastery(
        concept_id="cpt_c1",
        mastery_score=0.30,
        mastery_level=MasteryLevel.EMERGING,
        attempts=1,
        incorrect_attempts=1,
    ))
    mocks["adapt"].decide_next_action = MagicMock(return_value=AdaptationDecision(
        decision_id="adt_002",
        current_concept_id="cpt_c1",
        action=AdaptationAction.REMEDIATE_MISCONCEPTION,
        target_concept_id="cpt_c1",
        target_difficulty=DifficultyLevel.BEGINNER,
        reason="Severe misconception regarding collision inevitability.",
        mastery_score=0.30,
        misconception_ids=["msc_001"],
    ))
    mocks["adapt"].determine_adaptation = mocks["adapt"].decide_next_action

    req = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_c1", "cpt_c2"],
        available_time_minutes=20,
    )
    start_resp = await agent.start_teaching_session(req, db_session=async_db_session)
    sid = start_resp.session_id

    adv_req = AdvanceStepRequest(session_id=sid, learner_id="test_learner_01")
    await agent.advance_step(adv_req, db_session=async_db_session)
    q_resp = await agent.advance_step(adv_req, db_session=async_db_session)

    sub_req = SubmitAnswerRequest(
        session_id=sid,
        learner_id="test_learner_01",
        question_id=q_resp.question.question_id,
        answer_text="Hash tables cannot collide.",
    )
    ans_resp = await agent.submit_learner_answer(sub_req, db_session=async_db_session)

    assert ans_resp.evaluation.score == 0.30
    assert ans_resp.adaptation.action == AdaptationAction.REMEDIATE_MISCONCEPTION
    # Learner should stay on cpt_c1
    assert ans_resp.current_concept_id == "cpt_c1"
    assert ans_resp.concept_index == 0
    assert ans_resp.current_step == TeachingStep.EXPLAIN


@pytest.mark.asyncio
async def test_06_remediation_limit_anti_loop_guard(async_db_session, mock_agent_components):
    """Verify that after MAX_REMEDIATION_ATTEMPTS, the teacher advances forward to prevent infinite loops."""
    agent = mock_agent_components["agent"]
    mocks = mock_agent_components

    mocks["ans_eval"].evaluate_answer = AsyncMock(return_value=EvaluationResult(
        evaluation_id="eval_003",
        question_id="qst_mock_001",
        concept_id="cpt_c1",
        correctness=False,
        score=0.20,
        confidence=0.9,
        expected_answer="Correct Answer",
        student_answer="Wrong Answer",
        evidence="Inaccurate formulation.",
        feedback="Review the core concepts.",
    ))
    mocks["misc_det"].detect_misconceptions = AsyncMock(return_value=MisconceptionAnalysis(
        detected=True,
        misconceptions=[],
        overall_confidence=0.9,
        summary="Persistent struggle.",
    ))
    mocks["mastery"].update_mastery = MagicMock(return_value=ConceptMastery(
        concept_id="cpt_c1",
        mastery_score=0.20,
        mastery_level=MasteryLevel.EMERGING,
        attempts=3,
        incorrect_attempts=3,
    ))
    mocks["adapt"].decide_next_action = MagicMock(return_value=AdaptationDecision(
        decision_id="adt_003",
        current_concept_id="cpt_c1",
        action=AdaptationAction.RETEACH_CONCEPT,
        target_concept_id="cpt_c1",
        target_difficulty=DifficultyLevel.BEGINNER,
        reason="Struggling repeatedly.",
        mastery_score=0.20,
    ))
    mocks["adapt"].determine_adaptation = mocks["adapt"].decide_next_action

    # Pre-seed state with 2 remediation attempts already performed
    sess_svc = mocks["session_svc"]
    state = LessonSessionState(
        session_id="ses_loop_guard_test",
        learner_id="test_learner_01",
        concepts=["cpt_c1", "cpt_c2"],
        concept_names={"cpt_c1": "Concept 1", "cpt_c2": "Concept 2"},
        current_concept_index=0,
        current_step=TeachingStep.QUESTION,
        remediation_attempts={"cpt_c1": 2},  # Already at 2!
        last_question=Question(
            question_id="qst_mock_001",
            question_type=QuestionType.CONCEPTUAL,
            question_text="Diagnostic question",
            concept_id="cpt_c1",
            difficulty=DifficultyLevel.BEGINNER,
            learning_objective="Objective",
            correct_answer="Correct",
            explanation="Explanation",
        ),
    )
    await sess_svc.create_session(state, db_session=async_db_session)

    # Submitting another failing answer should trigger the anti-loop guard (> 2 attempts)
    sub_req = SubmitAnswerRequest(
        session_id="ses_loop_guard_test",
        learner_id="test_learner_01",
        question_id="qst_mock_001",
        answer_text="Still not understanding.",
    )
    ans_resp = await agent.submit_learner_answer(sub_req, db_session=async_db_session)

    # Must advance to next concept (cpt_c2) rather than looping indefinitely
    assert ans_resp.current_concept_id == "cpt_c2"
    assert ans_resp.concept_index == 1
    assert "revisit later" in ans_resp.message or "move ahead" in ans_resp.message


@pytest.mark.asyncio
async def test_07_session_persistence_and_restore(async_db_session, mock_agent_components):
    """Verify session state survives when in-memory cache is emptied and reloaded from DB."""
    agent = mock_agent_components["agent"]
    sess_svc = mock_agent_components["session_svc"]

    req = StartSessionRequest(
        learner_id="test_learner_01",
        topic="Database Indexing",
        concept_ids=["cpt_b_trees", "cpt_lsm_trees"],
        available_time_minutes=30,
    )
    resp = await agent.start_teaching_session(req, db_session=async_db_session)
    sid = resp.session_id

    # Clear in-memory cache to simulate restart
    sess_svc._cache.clear()

    # Retrieve from fresh cache; must query DB and rebuild LessonSessionState
    restored_state = await sess_svc.get_session(sid, db_session=async_db_session)
    assert restored_state is not None
    assert restored_state.session_id == sid
    assert restored_state.learner_id == "test_learner_01"
    assert restored_state.concepts == ["cpt_b_trees", "cpt_lsm_trees"]
    assert restored_state.time_budget_minutes == 30
    assert restored_state.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_08_multilingual_session_hinglish_hindi(async_db_session, mock_agent_components):
    """Verify sessions configured for Hindi and Hinglish retain language throughout delivery."""
    agent = mock_agent_components["agent"]

    req_hinglish = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_intro"],
        preferred_language=SupportedLanguage.HINGLISH,
    )
    resp_hinglish = await agent.start_teaching_session(req_hinglish, db_session=async_db_session)
    assert resp_hinglish.language == SupportedLanguage.HINGLISH
    assert resp_hinglish.delivery.language == SupportedLanguage.HINGLISH

    req_hindi = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_intro_2"],
        preferred_language=SupportedLanguage.HINDI,
    )
    resp_hindi = await agent.start_teaching_session(req_hindi, db_session=async_db_session)
    assert resp_hindi.language == SupportedLanguage.HINDI
    assert resp_hindi.delivery.language == SupportedLanguage.HINDI


@pytest.mark.asyncio
async def test_09_end_session_lifecycle(async_db_session, mock_agent_components):
    """Verify ending a session updates status to completed and records lesson completion in DB."""
    sess_svc = mock_agent_components["session_svc"]

    state = LessonSessionState(
        session_id="ses_end_test",
        learner_id="test_learner_01",
        lesson_id="lsn_algorithms_01",
        concepts=["cpt_c1"],
        status=SessionStatus.ACTIVE,
    )
    await sess_svc.create_session(state, db_session=async_db_session)

    ended_state = await sess_svc.end_session("ses_end_test", SessionStatus.COMPLETED, db_session=async_db_session)

    assert ended_state.status == SessionStatus.COMPLETED
    assert ended_state.current_step == TeachingStep.COMPLETE
    assert ended_state.ended_at is not None

    # Check that learner's completed_lessons list in DB contains lsn_algorithms_01
    repo = LearnerRepository(async_db_session)
    learner = await repo.get_learner("test_learner_01")
    assert "lsn_algorithms_01" in learner.completed_lessons


@pytest.mark.asyncio
async def test_10_time_budget_tracking(async_db_session, mock_agent_components):
    """Verify remaining time decrements across instructional steps and stays non-negative."""
    agent = mock_agent_components["agent"]

    req = StartSessionRequest(
        learner_id="test_learner_01",
        concept_ids=["cpt_quick_sort"],
        available_time_minutes=3,  # Short time budget
    )
    resp = await agent.start_teaching_session(req, db_session=async_db_session)
    assert resp.remaining_time_minutes == 3

    adv_req = AdvanceStepRequest(session_id=resp.session_id, learner_id="test_learner_01")
    resp_demo = await agent.advance_step(adv_req, db_session=async_db_session)
    assert resp_demo.remaining_time_minutes == 1

    resp_quest = await agent.advance_step(adv_req, db_session=async_db_session)
    assert resp_quest.remaining_time_minutes == 0  # Does not go below 0
