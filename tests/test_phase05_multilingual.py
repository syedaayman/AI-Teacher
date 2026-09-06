"""
Unit and Integration Tests for Phase 5: Multilingual AI Logic.

Verifies:
1. Mid-session language switching (English -> Hinglish -> Hindi) across instructional steps.
2. Immediate delivery re-rendering in the selected language.
3. Learner DB preference persistence and `LANGUAGE_CHANGED` event logging.
4. Cross-lingual answer evaluation (Hindi Devanagari and Hinglish answers evaluated against English questions).
5. Cross-lingual misconception detection (identifying flawed mental models expressed in Hinglish/Hindi).
6. Multilingual fallback question and delivery generation.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import LearningEvent, LearnerPreference
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
    RawAnswerEvaluationResponse,
    RawMisconceptionDetectionResponse,
    RawMisconceptionItem,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.schemas.session import (
    AdvanceStepRequest,
    InstructionalDelivery,
    LessonSessionState,
    SessionStatus,
    StartSessionRequest,
    TeachingStep,
)
from app.services.answer_evaluator import AnswerEvaluator
from app.services.misconception_detector import MisconceptionDetector
from app.services.session_service import SessionService
from app.services.teacher_agent import TeacherAgent
from app.services.teaching_content_engine import TeachingContentEngine


@pytest_asyncio.fixture
async def async_db_session():
    """Isolated in-memory SQLite database session for multilingual testing."""
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
        repo = LearnerRepository(session)
        await repo.create_learner(
            learner_id="multi_learner_01",
            name="Aarav Sharma",
            preferred_language="english",
            preferred_difficulty="intermediate",
        )
        yield session


# ============================================================================
# Test 1: Mid-Session Language Switching (Explain Step)
# ============================================================================

@pytest.mark.asyncio
async def test_mid_session_language_switch_explain(async_db_session: AsyncSession):
    """Switch language from English to Hinglish to Hindi during EXPLAIN step."""
    session_service = SessionService()
    mock_engine = MagicMock(spec=TeachingContentEngine)

    # Fallback/mock delivery generator that respects language
    async def mock_gen_explanation(*args, **kwargs):
        lang = kwargs.get("language", SupportedLanguage.ENGLISH)
        title_map = {
            SupportedLanguage.ENGLISH: "Foundations of Recursion",
            SupportedLanguage.HINGLISH: "Recursion Ka Conceptual Overview",
            SupportedLanguage.HINDI: "रिकर्सन की मूल अवधारणा",
        }
        return InstructionalDelivery(
            step=TeachingStep.EXPLAIN,
            concept_id="cpt_recursion",
            concept_name="Recursion",
            title=title_map.get(lang, "Recursion"),
            content=f"Explaining recursion in {lang.value}",
            visual_description="Call stack diagram",
            diagram_required=True,
            language=lang,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )

    mock_engine.generate_explanation = AsyncMock(side_effect=mock_gen_explanation)

    agent = TeacherAgent(session_svc=session_service, content_eng=mock_engine)

    # 1. Start session in English
    start_req = StartSessionRequest(
        learner_id="multi_learner_01",
        lesson_id="les_dsa_01",
        target_concept_ids=["cpt_recursion"],
        language=SupportedLanguage.ENGLISH,
    )
    init_res = await agent.start_teaching_session(start_req, db_session=async_db_session)
    assert init_res.language == SupportedLanguage.ENGLISH
    assert init_res.delivery.title == "Foundations of Recursion"

    # 2. Switch language to Hinglish mid-session
    hinglish_res = await agent.switch_session_language(
        session_id=init_res.session_id,
        new_language=SupportedLanguage.HINGLISH,
        db_session=async_db_session,
    )
    assert hinglish_res.language == SupportedLanguage.HINGLISH
    assert hinglish_res.delivery.language == SupportedLanguage.HINGLISH
    assert hinglish_res.delivery.title == "Recursion Ka Conceptual Overview"
    assert "Hinglish" in hinglish_res.message

    # Verify DB preference was updated to Hinglish
    repo = LearnerRepository(async_db_session)
    learner = await repo.get_learner("multi_learner_01")
    assert learner.preference.preferred_language == "hinglish"

    # Verify LANGUAGE_CHANGED event logged
    events_stmt = select(LearningEvent).where(
        LearningEvent.learner_id == "multi_learner_01",
        LearningEvent.event_type == "LANGUAGE_CHANGED",
    )
    events = (await async_db_session.execute(events_stmt)).scalars().all()
    assert len(events) == 1
    assert events[0].event_payload["old_language"] == "english"
    assert events[0].event_payload["new_language"] == "hinglish"

    # 3. Switch language to Hindi
    hindi_res = await agent.switch_session_language(
        session_id=init_res.session_id,
        new_language=SupportedLanguage.HINDI,
        db_session=async_db_session,
    )
    assert hindi_res.language == SupportedLanguage.HINDI
    assert hindi_res.delivery.language == SupportedLanguage.HINDI
    assert hindi_res.delivery.title == "रिकर्सन की मूल अवधारणा"

    learner_after = await repo.get_learner("multi_learner_01")
    assert learner_after.preference.preferred_language == "hindi"


# ============================================================================
# Test 2: Mid-Session Language Switching (Demonstrate Step)
# ============================================================================

@pytest.mark.asyncio
async def test_mid_session_language_switch_demonstrate(async_db_session: AsyncSession):
    """Switch language during DEMONSTRATE step re-renders demonstration."""
    session_service = SessionService()
    mock_engine = MagicMock(spec=TeachingContentEngine)

    mock_engine.generate_explanation = AsyncMock(
        return_value=InstructionalDelivery(
            step=TeachingStep.EXPLAIN,
            concept_id="cpt_trees",
            concept_name="Binary Trees",
            title="Trees Intro",
            content="Intro",
            language=SupportedLanguage.ENGLISH,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
    )

    async def mock_gen_demo(*args, **kwargs):
        lang = kwargs.get("language", SupportedLanguage.ENGLISH)
        title_map = {
            SupportedLanguage.ENGLISH: "Demonstration: Binary Trees in Action",
            SupportedLanguage.HINGLISH: "Binary Trees In Action: Step-by-Step Demo",
            SupportedLanguage.HINDI: "Binary Trees का व्यावहारिक उदाहरण",
        }
        return InstructionalDelivery(
            step=TeachingStep.DEMONSTRATE,
            concept_id="cpt_trees",
            concept_name="Binary Trees",
            title=title_map.get(lang, "Trees Demo"),
            content=f"Tree traversal code in {lang.value}",
            visual_description="Tree trace",
            diagram_required=True,
            language=lang,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )

    mock_engine.generate_demonstration = AsyncMock(side_effect=mock_gen_demo)

    agent = TeacherAgent(session_svc=session_service, content_eng=mock_engine)

    init_res = await agent.start_teaching_session(
        StartSessionRequest(
            learner_id="multi_learner_01",
            lesson_id="les_dsa_02",
            target_concept_ids=["cpt_trees"],
            language=SupportedLanguage.ENGLISH,
        ),
        db_session=async_db_session,
    )

    # Advance to DEMONSTRATE
    demo_res = await agent.advance_step(
        AdvanceStepRequest(
            session_id=init_res.session_id,
            learner_id="multi_learner_01",
        ),
        db_session=async_db_session,
    )
    assert demo_res.current_step == TeachingStep.DEMONSTRATE
    assert demo_res.delivery.title == "Demonstration: Binary Trees in Action"

    # Switch to Hinglish
    switch_res = await agent.switch_session_language(
        session_id=init_res.session_id,
        new_language=SupportedLanguage.HINGLISH,
        db_session=async_db_session,
    )
    assert switch_res.current_step == TeachingStep.DEMONSTRATE
    assert switch_res.delivery.language == SupportedLanguage.HINGLISH
    assert switch_res.delivery.title == "Binary Trees In Action: Step-by-Step Demo"


# ============================================================================
# Test 3: Cross-Lingual Evaluation: Hindi (Devanagari) Answer
# ============================================================================

@pytest.mark.asyncio
async def test_cross_lingual_answer_evaluation_hindi():
    """Verify Hindi answer to English question is evaluated on technical correctness without penalty."""
    mock_gemini = MagicMock()
    mock_gemini.generate_structured = AsyncMock(
        return_value=RawAnswerEvaluationResponse(
            score=0.95,
            correctness="correct",
            confidence=0.92,
            evidence="छात्र ने बेस केस और रिकर्सिव स्टेप दोनों को सही तरीके से समझाया है।",
            feedback="उत्कृष्ट उत्तर! आपने रिकर्सन के दोनों मुख्य घटकों को स्पष्ट रूप से प्रस्तुत किया है।",
            concepts_demonstrated=["base_case", "recursive_call", "stack_frame"],
            concepts_missing=[],
            rubric_adherence="Accurately identified terminating condition and self-referential call.",
        )
    )

    evaluator = AnswerEvaluator(client=mock_gemini)

    question = Question(
        question_id="qst_rec_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain the two essential components required for a recursive function to terminate correctly.",
        concept_id="cpt_recursion",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Understand recursive termination conditions",
        options=[],
        correct_answer="A recursive function requires a base case to terminate and a recursive case that moves towards the base case.",
        explanation="Without a base case, recursion leads to stack overflow.",
    )

    hindi_submission = StudentAnswer(
        question_id="qst_rec_01",
        concept_id="cpt_recursion",
        answer_text="रिकर्सिव फ़ंक्शन के लिए पहला घटक 'बेस केस' (Base Case) होता है जो आगे के कॉल्स को रोकता है, और दूसरा घटक वह रिकर्सिव कॉल है जो इनपुट को बेस केस की ओर ले जाता है।",
        reasoning="अगर बेस केस नहीं होगा तो कॉल स्टैक भर जाएगा और स्टैक ओवरफ़्लो एरर आएगा।",
    )

    result = await evaluator.evaluate_answer(question=question, student_answer=hindi_submission)

    assert result.score == 0.95
    assert result.correctness is True
    assert "base_case" in result.concepts_demonstrated

    # Inspect the prompt passed to Gemini to ensure Multilingual instructions were included
    call_args = mock_gemini.generate_structured.call_args
    sys_instruction = call_args.kwargs["system_instruction"]
    prompt = call_args.kwargs["prompt"]

    assert "Multilingual & Cross-Lingual Evaluation" in sys_instruction
    assert "Hindi (Devanagari script)" in sys_instruction
    assert "रिकर्सिव फ़ंक्शन" in prompt


# ============================================================================
# Test 4: Cross-Lingual Evaluation: Hinglish Answer
# ============================================================================

@pytest.mark.asyncio
async def test_cross_lingual_answer_evaluation_hinglish():
    """Verify conversational Hinglish answer receives high score for conceptual clarity."""
    mock_gemini = MagicMock()
    mock_gemini.generate_structured = AsyncMock(
        return_value=RawAnswerEvaluationResponse(
            score=1.0,
            correctness="correct",
            confidence=0.95,
            evidence="Student accurately explained that BST maintains left < root < right invariant.",
            feedback="Bilkul sahi! Aapne BST ki property ko perfectly explain kiya hai.",
            concepts_demonstrated=["binary_search_tree", "ordering_invariant", "lookup_efficiency"],
            concepts_missing=[],
            rubric_adherence="Fully satisfied technical ordering requirements in Hinglish.",
        )
    )

    evaluator = AnswerEvaluator(client=mock_gemini)

    question = Question(
        question_id="qst_bst_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="What ordering property must hold for every node in a Binary Search Tree (BST)?",
        concept_id="cpt_bst",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Understand BST ordering invariant",
        options=[],
        correct_answer="For any node, all keys in the left subtree must be less, and all keys in the right subtree must be greater.",
        explanation="This property enables O(log n) average search time.",
    )

    hinglish_submission = StudentAnswer(
        question_id="qst_bst_01",
        concept_id="cpt_bst",
        answer_text="BST me kisi bhi node ke left child me saari values us node se chhoti hoti hain, aur right child me saari values badi hoti hain. Ye rule pure tree ke har subtree pe lagta hai.",
        reasoning="Is property ki wajah se hum bina pure tree ko scan kiye binary search jaisi O(log n) speed me search kar sakte hain.",
    )

    result = await evaluator.evaluate_answer(question=question, student_answer=hinglish_submission)

    assert result.score == 1.0
    assert result.correctness is True
    assert len(result.concepts_missing) == 0

    call_args = mock_gemini.generate_structured.call_args
    prompt = call_args.kwargs["prompt"]
    assert "BST me kisi bhi node" in prompt


# ============================================================================
# Test 5: Cross-Lingual Misconception Detection (Hinglish/Hindi Phrasing)
# ============================================================================

@pytest.mark.asyncio
async def test_cross_lingual_misconception_detection():
    """Verify misconception detector flags flawed reasoning expressed in Hinglish."""
    mock_gemini = MagicMock()
    mock_gemini.generate_structured = AsyncMock(
        return_value=RawMisconceptionDetectionResponse(
            is_genuine_misconception=True,
            misconceptions=[
                RawMisconceptionItem(
                    description="Believes that recursion eliminates the need for base cases and infinite stack frames exist without overflow.",
                    evidence="Student states: 'recursion me base case option hai, loop ki tarah compiler khud break kar deta hai'",
                    severity="high",
                    confidence=0.94,
                    remediation_strategy="Explain call stack frames and show stack overflow trace when base condition is absent.",
                    is_prerequisite_flaw=False,
                )
            ],
            summary="Flawed mental model regarding recursive termination and call stack memory allocation.",
        )
    )

    detector = MisconceptionDetector(client=mock_gemini)

    question = Question(
        question_id="qst_rec_02",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Why is a base case mandatory in recursion?",
        concept_id="cpt_recursion",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Understand stack frame exhaustion without base cases",
        options=[],
        correct_answer="It halts repeated calls to prevent unbounded stack growth.",
        explanation="Missing base cases trigger RecursionError / StackOverflowError.",
    )

    student_answer = StudentAnswer(
        question_id="qst_rec_02",
        concept_id="cpt_recursion",
        answer_text="Recursion me base case option hai, loop ki tarah compiler khud break kar deta hai jab memory full hone lagti hai.",
        reasoning="Modern compilers infinite recursion ko optimize karke handle kar lete hain.",
    )

    eval_result = EvaluationResult(
        evaluation_id="eval_rec_02",
        question_id="qst_rec_02",
        concept_id="cpt_recursion",
        student_answer=student_answer.answer_text,
        expected_answer=question.correct_answer,
        score=0.1,
        correctness=False,
        confidence=0.9,
        concepts_demonstrated=[],
        concepts_missing=["call_stack_overflow", "termination_condition"],
        evidence="Student falsely claims compiler handles unbounded recursion without base case.",
        feedback="Incorrect. Compilers cannot infer when to terminate recursion without an explicit base case.",
    )

    analysis = await detector.detect_misconceptions(
        question=question,
        student_answer=student_answer,
        evaluation_result=eval_result,
    )

    assert analysis.detected is True
    assert len(analysis.misconceptions) == 1
    assert analysis.misconceptions[0].severity == MisconceptionSeverity.HIGH

    call_args = mock_gemini.generate_structured.call_args
    sys_instruction = call_args.kwargs["system_instruction"]
    assert "Multilingual & Idiomatic Recognition" in sys_instruction
    assert "Hinglish" in sys_instruction


# ============================================================================
# Test 6: Multilingual Fallback Question Generation
# ============================================================================

@pytest.mark.asyncio
async def test_multilingual_fallback_question_generation():
    """Verify deterministic fallback questions generated in Hindi, Hinglish, and English."""
    agent = TeacherAgent()

    # Force fallback by passing invalid generator or triggering exception
    agent._question_generator.generate_question = AsyncMock(side_effect=RuntimeError("LLM API Offline"))

    # Hindi question
    q_hi = await agent._generate_concept_question(
        concept_id="cpt_hash_map",
        concept_name="Hash Map",
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.HINDI,
    )
    assert "मूलभूत सिद्धांत" in q_hi.question_text
    assert "Hash Map" in q_hi.question_text

    # Hinglish question
    q_hinglish = await agent._generate_concept_question(
        concept_id="cpt_hash_map",
        concept_name="Hash Map",
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.HINGLISH,
    )
    assert "fundamental mechanism" in q_hinglish.question_text
    assert "explain kijiye" in q_hinglish.question_text

    # English question
    q_en = await agent._generate_concept_question(
        concept_id="cpt_hash_map",
        concept_name="Hash Map",
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
    )
    assert "Explain the fundamental mechanism and importance of Hash Map" in q_en.question_text


# ============================================================================
# Test 7: Teaching Content Engine Fallback Delivery in Hindi & Hinglish
# ============================================================================

def test_teaching_content_engine_multilingual_fallbacks():
    """Verify deterministic fallback explanation, demonstration, and remediation in Hindi and Hinglish."""
    engine = TeachingContentEngine()

    # 1. Hindi Explanation
    exp_hi = engine._build_fallback_explanation(
        concept_id="cpt_pointers",
        concept_name="Pointers",
        difficulty=DifficultyLevel.BEGINNER,
        language=SupportedLanguage.HINDI,
        depth="standard",
    )
    assert "अवधारणा" in exp_hi.title
    assert "पुस्तकालय" in exp_hi.analogy
    assert exp_hi.language == SupportedLanguage.HINDI

    # 2. Hinglish Demonstration
    demo_hinglish = engine._build_fallback_demonstration(
        concept_id="cpt_pointers",
        concept_name="Pointers",
        difficulty=DifficultyLevel.BEGINNER,
        language=SupportedLanguage.HINGLISH,
        depth="standard",
    )
    assert "Pointers In Action" in demo_hinglish.title
    assert "step-by-step" in demo_hinglish.content
    assert demo_hinglish.code_snippet is not None
    assert demo_hinglish.language == SupportedLanguage.HINGLISH

    # 3. Hindi Remediation
    rem_hi = engine._build_fallback_remediation(
        concept_id="cpt_pointers",
        concept_name="Pointers",
        misconception_text="पॉइंटर्स केवल सीधे मान संग्रहीत करते हैं",
        difficulty=DifficultyLevel.BEGINNER,
        language=SupportedLanguage.HINDI,
    )
    assert "निवारण और स्पष्टीकरण" in rem_hi.title
    assert rem_hi.counter_example is not None
    assert rem_hi.language == SupportedLanguage.HINDI
