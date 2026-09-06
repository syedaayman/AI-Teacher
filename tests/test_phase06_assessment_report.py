"""
Unit and Integration Tests for Phase 6: Final Assessment and Comprehensive Learning Report.

Verifies:
1. Balanced multi-question final assessment generation across curriculum concepts.
2. Comprehensive assessment evaluation, scoring, letter grade, and mastery categorization.
3. Concept-by-concept diagnostic breakdowns (mastered, in_progress, needs_review).
4. Misconception diagnosis aggregation across the final assessment.
5. Persistent audit logging: AssessmentAttempt records, running average score,
   ConceptMasteryRecord upserts, and LearningEvent logs.
6. Multilingual reporting (English, Hindi, Hinglish).
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import AssessmentAttempt, ConceptMasteryRecord, Learner, LearningEvent
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.adaptive import MasteryLevel
from app.schemas.assessment import (
    AssessmentReport,
    ConceptReportItem,
    EvaluationResult,
    FinalAssessmentPackage,
    FinalAssessmentRequest,
    FinalAssessmentSubmission,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
    RawAssessmentReportPayload,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel
from app.services.answer_evaluator import AnswerEvaluator
from app.services.assessment_report_service import AssessmentReportService
from app.services.concept_service import ConceptService
from app.services.misconception_detector import MisconceptionDetector
from app.services.question_generator import QuestionGenerator


@pytest_asyncio.fixture
async def async_db_session():
    """Isolated in-memory SQLite database session for assessment report testing."""
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
            learner_id="test_exam_learner",
            name="Ramanujan",
            preferred_language="english",
            preferred_difficulty="intermediate",
        )
        yield session


# ============================================================================
# Test 1: Assessment Package Generation
# ============================================================================

@pytest.mark.asyncio
async def test_generate_final_assessment():
    """Verify assessment generation distributes questions across concepts."""
    mock_gen = MagicMock(spec=QuestionGenerator)

    async def mock_generate_question(concept, question_type, *args, **kwargs):
        return Question(
            question_id=f"qst_{concept.concept_id}_{question_type.value}",
            question_type=question_type,
            question_text=f"Test question for {concept.name}",
            concept_id=concept.concept_id,
            difficulty=DifficultyLevel.INTERMEDIATE,
            learning_objective=f"Assess {concept.name}",
            options=["A", "B", "C", "D"] if question_type == QuestionType.MCQ else [],
            correct_answer="Correct",
            explanation="Explanation",
        )

    mock_gen.generate_question = AsyncMock(side_effect=mock_generate_question)

    mock_concepts = MagicMock(spec=ConceptService)
    mock_concepts.get_concept = MagicMock(
        side_effect=lambda cid: Concept(
            concept_id=cid,
            name=cid.replace("cpt_", "").title(),
            description="Concept desc",
            difficulty=DifficultyLevel.INTERMEDIATE,
            learning_objectives=["Obj"],
        )
    )

    service = AssessmentReportService(
        question_gen=mock_gen,
        concept_svc=mock_concepts,
    )

    req = FinalAssessmentRequest(
        learner_id="test_exam_learner",
        concept_ids=["cpt_stacks", "cpt_queues", "cpt_heaps"],
        num_questions=6,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
    )

    package = await service.generate_assessment(req)

    assert package.total_questions == 6
    assert len(package.questions) == 6
    assert package.learner_id == "test_exam_learner"
    cids_tested = {q.concept_id for q in package.questions}
    assert cids_tested == {"cpt_stacks", "cpt_queues", "cpt_heaps"}


# ============================================================================
# Test 2: Multi-Question Evaluation & Report Synthesis
# ============================================================================

@pytest.mark.asyncio
async def test_evaluate_final_assessment_scoring_and_report():
    """Verify score calculation, letter grade, concept breakdown, and narrative synthesis."""
    mock_eval = MagicMock(spec=AnswerEvaluator)
    mock_detector = MagicMock(spec=MisconceptionDetector)

    # 3 answers: 2 high scores, 1 low score
    eval_map = {
        "q1": EvaluationResult(
            evaluation_id="eval_1",
            question_id="q1",
            concept_id="cpt_trees",
            correctness=True,
            score=1.0,
            confidence=0.9,
            expected_answer="Ans 1",
            student_answer="Tree traversal answer",
            evidence="Evidence 1",
            feedback="Great",
        ),
        "q2": EvaluationResult(
            evaluation_id="eval_2",
            question_id="q2",
            concept_id="cpt_trees",
            correctness=True,
            score=0.8,
            confidence=0.9,
            expected_answer="Ans 2",
            student_answer="Tree search answer",
            evidence="Evidence 2",
            feedback="Good",
        ),
        "q3": EvaluationResult(
            evaluation_id="eval_3",
            question_id="q3",
            concept_id="cpt_graphs",
            correctness=False,
            score=0.3,
            confidence=0.85,
            expected_answer="Ans 3",
            student_answer="Graph cycles flawed answer",
            evidence="Evidence 3",
            feedback="Needs work",
        ),
    }

    mock_eval.evaluate_answer = AsyncMock(
        side_effect=lambda question, student_answer: eval_map[question.question_id]
    )

    mock_detector.detect_misconceptions = AsyncMock(
        return_value=MisconceptionAnalysis(
            detected=True,
            misconceptions=[
                Misconception(
                    misconception_id="m_graph_cycle",
                    concept_id="cpt_graphs",
                    description="Confuses DAG topological sort with general cycle detection",
                    evidence="Student claimed topological sort exists on all graphs",
                    severity=MisconceptionSeverity.HIGH,
                    source_question_id="q3",
                )
            ],
            overall_confidence=0.9,
            summary="DAG misconception",
        )
    )

    service = AssessmentReportService(
        answer_eval=mock_eval,
        misc_det=mock_detector,
    )

    questions = [
        Question(
            question_id="q1",
            question_type=QuestionType.CONCEPTUAL,
            question_text="Q1 text",
            concept_id="cpt_trees",
            difficulty=DifficultyLevel.INTERMEDIATE,
            learning_objective="Obj 1",
            options=[],
            correct_answer="Ans 1",
            explanation="Exp 1",
        ),
        Question(
            question_id="q2",
            question_type=QuestionType.CONCEPTUAL,
            question_text="Q2 text",
            concept_id="cpt_trees",
            difficulty=DifficultyLevel.INTERMEDIATE,
            learning_objective="Obj 2",
            options=[],
            correct_answer="Ans 2",
            explanation="Exp 2",
        ),
        Question(
            question_id="q3",
            question_type=QuestionType.CONCEPTUAL,
            question_text="Q3 text",
            concept_id="cpt_graphs",
            difficulty=DifficultyLevel.INTERMEDIATE,
            learning_objective="Obj 3",
            options=[],
            correct_answer="Ans 3",
            explanation="Exp 3",
        ),
    ]

    submission = FinalAssessmentSubmission(
        assessment_id="asm_test_01",
        learner_id="test_exam_learner",
        answers=[
            StudentAnswer(question_id="q1", answer_text="Tree traversal answer"),
            StudentAnswer(question_id="q2", answer_text="Tree search answer"),
            StudentAnswer(question_id="q3", answer_text="Graph cycles flawed answer"),
        ],
        language=SupportedLanguage.ENGLISH,
    )

    report = await service.evaluate_assessment(submission, questions=questions)

    # Average score: (1.0 + 0.8 + 0.3) / 3 = 0.70
    assert report.overall_score == 0.70
    assert report.letter_grade == "B"
    assert report.overall_mastery_level == MasteryLevel.PROFICIENT
    assert report.total_questions == 3
    assert report.correct_answers == 2

    # Concept breakdown
    cb_map = {cb.concept_id: cb for cb in report.concept_breakdowns}
    assert cb_map["cpt_trees"].score == 0.90
    assert cb_map["cpt_trees"].status == "mastered"
    assert cb_map["cpt_graphs"].score == 0.30
    assert cb_map["cpt_graphs"].status == "needs_review"

    # Misconceptions
    assert len(report.misconceptions_detected) == 1
    assert "DAG" in report.misconceptions_detected[0].description

    # Narrative recommendations
    assert len(report.strengths) >= 1
    assert len(report.recommendations) >= 1


# ============================================================================
# Test 3: Persistent Database Audit Logging
# ============================================================================

@pytest.mark.asyncio
async def test_evaluate_final_assessment_persistence(async_db_session: AsyncSession):
    """Verify AssessmentAttempt records, running average score, and event logs in DB."""
    mock_eval = MagicMock(spec=AnswerEvaluator)
    mock_eval.evaluate_answer = AsyncMock(
        return_value=EvaluationResult(
            evaluation_id="eval_persist_01",
            question_id="q_persist",
            concept_id="cpt_memory",
            correctness=True,
            score=0.95,
            confidence=0.92,
            expected_answer="Reference Answer",
            student_answer="Student Answer",
            concepts_demonstrated=["memory_allocation"],
            concepts_missing=[],
            evidence="Clean explanation",
            feedback="Well done",
        )
    )

    service = AssessmentReportService(answer_eval=mock_eval)

    question = Question(
        question_id="q_persist",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain virtual memory paging.",
        concept_id="cpt_memory",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Memory paging",
        options=[],
        correct_answer="Reference Answer",
        explanation="Explanation",
    )

    submission = FinalAssessmentSubmission(
        assessment_id="asm_persist_01",
        learner_id="test_exam_learner",
        answers=[StudentAnswer(question_id="q_persist", answer_text="Student Answer")],
        language=SupportedLanguage.ENGLISH,
    )

    report = await service.evaluate_assessment(
        submission,
        questions=[question],
        db_session=async_db_session,
    )

    # 1. Check AssessmentAttempt in DB
    stmt_att = select(AssessmentAttempt).where(AssessmentAttempt.id == "eval_persist_01")
    attempt = (await async_db_session.execute(stmt_att)).scalar_one_or_none()
    assert attempt is not None
    assert attempt.learner_id == "test_exam_learner"
    assert attempt.score == 0.95
    assert attempt.correctness is True

    # 2. Check Learner stats updated
    repo = LearnerRepository(async_db_session)
    learner = await repo.get_learner("test_exam_learner")
    assert learner.assessment_count == 1
    assert learner.average_score == 0.95

    # 3. Check ConceptMasteryRecord upserted
    stmt_cm = select(ConceptMasteryRecord).where(
        ConceptMasteryRecord.learner_id == "test_exam_learner",
        ConceptMasteryRecord.concept_id == "cpt_memory",
    )
    cm_rec = (await async_db_session.execute(stmt_cm)).scalar_one_or_none()
    assert cm_rec is not None
    assert cm_rec.mastery_score == 0.95
    assert cm_rec.mastery_level == "mastered"

    # 4. Check LearningEvent logged
    stmt_ev = select(LearningEvent).where(
        LearningEvent.learner_id == "test_exam_learner",
        LearningEvent.event_type == "FINAL_ASSESSMENT_COMPLETED",
    )
    event = (await async_db_session.execute(stmt_ev)).scalar_one_or_none()
    assert event is not None
    assert event.event_payload["overall_score"] == 0.95
    assert event.event_payload["letter_grade"] == "A+"


# ============================================================================
# Test 4: Multilingual Diagnostic Reports (Hindi and Hinglish)
# ============================================================================

def test_multilingual_assessment_narrative_fallbacks():
    """Verify deterministic fallback report generation in Hindi and Hinglish."""
    service = AssessmentReportService()
    breakdowns = [
        ConceptReportItem(
            concept_id="cpt_algo",
            concept_name="Dynamic Programming",
            score=0.9,
            mastery_level=MasteryLevel.MASTERED,
            status="mastered",
        ),
        ConceptReportItem(
            concept_id="cpt_graph",
            concept_name="Shortest Paths",
            score=0.4,
            mastery_level=MasteryLevel.DEVELOPING,
            status="needs_review",
        ),
    ]
    misc = [
        Misconception(
            misconception_id="m1",
            concept_id="cpt_graph",
            description="Believes Dijkstra works with negative edge weights",
            evidence="evidence",
            severity=MisconceptionSeverity.HIGH,
            source_question_id="q1",
        )
    ]

    # Hindi
    hindi_nar = service._build_fallback_narrative(
        overall_score=0.65,
        letter_grade="C",
        concept_breakdowns=breakdowns,
        misconceptions=misc,
        language=SupportedLanguage.HINDI,
    )
    assert "मूल्यांकन संपन्न" in hindi_nar.summary
    assert "मजबूत वैचारिक स्पष्टता" in hindi_nar.strengths[0]
    assert "अभ्यास" in hindi_nar.weaknesses[0]

    # Hinglish
    hinglish_nar = service._build_fallback_narrative(
        overall_score=0.65,
        letter_grade="C",
        concept_breakdowns=breakdowns,
        misconceptions=misc,
        language=SupportedLanguage.HINGLISH,
    )
    assert "Assessment successfully complete ho gaya" in hinglish_nar.summary
    assert "clear understanding" in hinglish_nar.strengths[0]
    assert "revision" in hinglish_nar.weaknesses[0]


# ============================================================================
# Test 5: Letter Grade and Mastery Level Derivations
# ============================================================================

def test_grade_and_mastery_level_derivations():
    """Test standard grade and mastery categorization thresholds."""
    service = AssessmentReportService()

    assert service._derive_letter_grade(0.95) == "A+"
    assert service._derive_letter_grade(0.85) == "A"
    assert service._derive_letter_grade(0.75) == "B"
    assert service._derive_letter_grade(0.65) == "C"
    assert service._derive_letter_grade(0.55) == "D"
    assert service._derive_letter_grade(0.40) == "F"

    assert service._derive_mastery_level(0.90) == MasteryLevel.MASTERED
    assert service._derive_mastery_level(0.75) == MasteryLevel.PROFICIENT
    assert service._derive_mastery_level(0.60) == MasteryLevel.DEVELOPING
    assert service._derive_mastery_level(0.30) == MasteryLevel.EMERGING
    assert service._derive_mastery_level(0.10) == MasteryLevel.NOT_STARTED
