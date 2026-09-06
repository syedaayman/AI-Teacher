"""
Integration tests for Phase 8: REST APIs & Full End-to-End Integration.

Verifies:
1. Teaching session API lifecycle: start, advance, submit-answer, switch-language, get, and end.
2. Final assessment generation and comprehensive diagnostic report evaluation APIs.
3. Spaced repetition memory update, review queue, and longitudinal summary APIs.
"""

from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pytest

from app.core.exceptions import InvalidSessionStateError
from main import app
from app.schemas.adaptive import MasteryLevel, MemoryUpdateResult, ReviewItem, ReviewQueue
from app.schemas.assessment import (
    AssessmentReport,
    ConceptReportItem,
    EvaluationResult,
    FinalAssessmentPackage,
    Misconception,
    MisconceptionSeverity,
    Question,
    QuestionType,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.schemas.session import (
    InstructionalDelivery,
    LessonSessionState,
    SessionStatus,
    SessionStepResponse,
    TeachingStep,
)
from app.services.assessment_report_service import assessment_report_service
from app.services.learning_memory_service import learning_memory_service
from app.services.session_service import session_service
from app.services.teacher_agent import teacher_agent

client = TestClient(app)


# ============================================================================
# Test 1: Teaching Session Endpoints Lifecycle
# ============================================================================

def test_api_sessions_lifecycle(monkeypatch):
    """Test full HTTP API lifecycle of an adaptive teaching session."""
    dummy_delivery = InstructionalDelivery(
        step=TeachingStep.EXPLAIN,
        concept_id="cpt_api_test",
        concept_name="API Testing",
        title="Testing Concepts",
        content="Explaining how API integration functions.",
        language=SupportedLanguage.ENGLISH,
        difficulty=DifficultyLevel.INTERMEDIATE,
    )

    mock_start_res = SessionStepResponse(
        session_id="ses_api_123",
        learner_id="test_api_learner",
        current_step=TeachingStep.EXPLAIN,
        status=SessionStatus.ACTIVE,
        current_concept_id="cpt_api_test",
        current_concept_name="API Testing",
        concept_index=0,
        total_concepts=1,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
        remaining_time_minutes=20,
        delivery=dummy_delivery,
        message="Welcome to your session",
    )

    # 1. Start Session
    monkeypatch.setattr(
        teacher_agent,
        "start_teaching_session",
        AsyncMock(return_value=mock_start_res),
    )

    start_payload = {
        "learner_id": "test_api_learner",
        "concept_ids": ["cpt_api_test"],
        "available_time_minutes": 20,
        "desired_depth": "standard",
    }
    resp = client.post("/api/v1/sessions/start", json=start_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"] == "ses_api_123"
    assert data["current_step"] == "explain"
    assert data["delivery"]["title"] == "Testing Concepts"

    # 2. Advance Step to DEMONSTRATE
    mock_advance_res = SessionStepResponse(
        session_id="ses_api_123",
        learner_id="test_api_learner",
        current_step=TeachingStep.DEMONSTRATE,
        status=SessionStatus.ACTIVE,
        current_concept_id="cpt_api_test",
        current_concept_name="API Testing",
        concept_index=0,
        total_concepts=1,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
        remaining_time_minutes=18,
        delivery=InstructionalDelivery(
            step=TeachingStep.DEMONSTRATE,
            concept_id="cpt_api_test",
            concept_name="API Testing",
            title="Demo in Action",
            content="Showing code demonstration.",
            language=SupportedLanguage.ENGLISH,
            difficulty=DifficultyLevel.INTERMEDIATE,
        ),
        message="Demonstration phase",
    )
    monkeypatch.setattr(
        teacher_agent,
        "advance_step",
        AsyncMock(return_value=mock_advance_res),
    )

    advance_payload = {
        "session_id": "ses_api_123",
        "learner_id": "test_api_learner",
    }
    resp = client.post("/api/v1/sessions/advance", json=advance_payload)
    assert resp.status_code == 200
    assert resp.json()["current_step"] == "demonstrate"

    # 3. Submit Answer
    mock_eval = EvaluationResult(
        evaluation_id="eval_api_01",
        question_id="q_api_01",
        concept_id="cpt_api_test",
        correctness=True,
        score=0.95,
        confidence=0.9,
        expected_answer="Expected",
        student_answer="My answer",
        evidence="Good logic",
        feedback="Well done!",
    )
    mock_answer_res = SessionStepResponse(
        session_id="ses_api_123",
        learner_id="test_api_learner",
        current_step=TeachingStep.EXPLAIN,
        status=SessionStatus.ACTIVE,
        current_concept_id="cpt_api_test",
        current_concept_name="API Testing",
        concept_index=0,
        total_concepts=1,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.ENGLISH,
        remaining_time_minutes=16,
        evaluation=mock_eval,
        message="Answer evaluated",
    )
    monkeypatch.setattr(
        teacher_agent,
        "submit_answer",
        AsyncMock(return_value=mock_answer_res),
    )

    answer_payload = {
        "session_id": "ses_api_123",
        "learner_id": "test_api_learner",
        "question_id": "q_api_01",
        "answer_text": "My answer",
    }
    resp = client.post("/api/v1/sessions/submit-answer", json=answer_payload)
    assert resp.status_code == 200
    assert resp.json()["evaluation"]["score"] == 0.95

    # 4. Switch Language to Hinglish
    mock_switch_res = SessionStepResponse(
        session_id="ses_api_123",
        learner_id="test_api_learner",
        current_step=TeachingStep.EXPLAIN,
        status=SessionStatus.ACTIVE,
        current_concept_id="cpt_api_test",
        current_concept_name="API Testing",
        concept_index=0,
        total_concepts=1,
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.HINGLISH,
        remaining_time_minutes=16,
        message="Language switched to Hinglish",
    )
    monkeypatch.setattr(
        teacher_agent,
        "switch_session_language",
        AsyncMock(return_value=mock_switch_res),
    )

    switch_payload = {
        "session_id": "ses_api_123",
        "language": "hinglish",
    }
    resp = client.post("/api/v1/sessions/switch-language", json=switch_payload)
    assert resp.status_code == 200
    assert resp.json()["language"] == "hinglish"

    # 5. Get Session State
    mock_state = LessonSessionState(
        session_id="ses_api_123",
        learner_id="test_api_learner",
        current_step=TeachingStep.EXPLAIN,
        status=SessionStatus.ACTIVE,
        concepts=["cpt_api_test"],
        difficulty=DifficultyLevel.INTERMEDIATE,
        language=SupportedLanguage.HINGLISH,
    )
    monkeypatch.setattr(
        session_service,
        "get_session",
        AsyncMock(return_value=mock_state),
    )

    resp = client.get("/api/v1/sessions/ses_api_123")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "ses_api_123"

    # 6. End Session
    mock_state.status = SessionStatus.COMPLETED
    monkeypatch.setattr(
        session_service,
        "end_session",
        AsyncMock(return_value=mock_state),
    )
    resp = client.post("/api/v1/sessions/ses_api_123/end?final_status=completed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# ============================================================================
# Test 2: Final Assessment & Comprehensive Learning Report APIs
# ============================================================================

def test_api_final_assessment_and_reporting(monkeypatch):
    """Test generating final exam packages and submitting for comprehensive report."""
    mock_package = FinalAssessmentPackage(
        assessment_id="asm_api_99",
        learner_id="test_api_learner",
        questions=[
            Question(
                question_id="q_final_01",
                question_type=QuestionType.CONCEPTUAL,
                question_text="Final question on testing",
                concept_id="cpt_api_test",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objective="Assess testing",
                options=[],
                correct_answer="Correct Answer",
                explanation="Explanation",
            )
        ],
        total_questions=1,
    )
    monkeypatch.setattr(
        assessment_report_service,
        "generate_assessment",
        AsyncMock(return_value=mock_package),
    )

    gen_payload = {
        "learner_id": "test_api_learner",
        "concept_ids": ["cpt_api_test"],
        "num_questions": 1,
    }
    resp = client.post("/api/v1/assessment/final/generate", json=gen_payload)
    assert resp.status_code == 201
    assert resp.json()["assessment_id"] == "asm_api_99"
    assert len(resp.json()["questions"]) == 1

    # Evaluate Final Assessment
    mock_report = AssessmentReport(
        report_id="rpt_api_99",
        learner_id="test_api_learner",
        overall_score=0.92,
        overall_mastery_level=MasteryLevel.MASTERED,
        letter_grade="A+",
        total_questions=1,
        correct_answers=1,
        concept_breakdowns=[
            ConceptReportItem(
                concept_id="cpt_api_test",
                concept_name="API Testing",
                score=0.92,
                mastery_level=MasteryLevel.MASTERED,
                status="mastered",
                attempts=1,
            )
        ],
        misconceptions_detected=[],
        strengths=["Solid grasp of automated testing"],
        weaknesses=[],
        recommendations=["Continue to advanced integration testing"],
        summary="Outstanding final assessment performance.",
        language=SupportedLanguage.ENGLISH,
    )
    monkeypatch.setattr(
        assessment_report_service,
        "evaluate_assessment",
        AsyncMock(return_value=mock_report),
    )

    eval_payload = {
        "assessment_id": "asm_api_99",
        "learner_id": "test_api_learner",
        "answers": [
            {"question_id": "q_final_01", "answer_text": "My final answer"}
        ],
        "language": "english",
    }
    resp = client.post("/api/v1/assessment/final/evaluate", json=eval_payload)
    assert resp.status_code == 200
    report_data = resp.json()
    assert report_data["report_id"] == "rpt_api_99"
    assert report_data["letter_grade"] == "A+"
    assert report_data["overall_score"] == 0.92
    assert len(report_data["concept_breakdowns"]) == 1


# ============================================================================
# Test 3: Spaced Repetition Memory & Review Queue APIs
# ============================================================================

def test_api_memory_and_spaced_repetition(monkeypatch):
    """Test memory updates, review queue retrieval, and longitudinal analytics."""
    # 1. Update concept memory
    mock_update_res = MemoryUpdateResult(
        concept_id="cpt_api_test",
        old_interval_days=1.0,
        new_interval_days=6.0,
        old_easiness_factor=2.5,
        new_easiness_factor=2.6,
        repetition_number=2,
        next_review_due_at="2026-09-10T12:00:00Z",
        retention_probability=1.0,
    )
    monkeypatch.setattr(
        learning_memory_service,
        "update_concept_memory",
        AsyncMock(return_value=mock_update_res),
    )

    update_payload = {
        "concept_id": "cpt_api_test",
        "score": 0.95,
    }
    resp = client.post("/api/v1/memory/test_api_learner/update", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["new_interval_days"] == 6.0
    assert resp.json()["repetition_number"] == 2

    # 2. Get review queue
    mock_queue = ReviewQueue(
        learner_id="test_api_learner",
        total_due=1,
        items=[
            ReviewItem(
                concept_id="cpt_api_test",
                concept_name="API Testing",
                mastery_score=0.70,
                mastery_level=MasteryLevel.PROFICIENT,
                retention_probability=0.74,
                interval_days=6.0,
                repetition_number=2,
                days_since_last_review=7.0,
                urgency_score=0.35,
                recommended_action="review_now",
            )
        ],
        generated_at="2026-09-04T12:00:00Z",
    )
    monkeypatch.setattr(
        learning_memory_service,
        "get_review_queue",
        AsyncMock(return_value=mock_queue),
    )

    resp = client.get("/api/v1/memory/test_api_learner/queue?max_items=5")
    assert resp.status_code == 200
    assert resp.json()["total_due"] == 1
    assert resp.json()["items"][0]["recommended_action"] == "review_now"

    # 3. Get historical summary
    mock_summary = {
        "learner_id": "test_api_learner",
        "name": "API Learner",
        "overall_mastery": 0.88,
        "average_score": 0.90,
        "total_assessments_taken": 4,
        "total_sessions": 2,
        "total_questions_attempted": 8,
        "total_concepts_tracked": 3,
        "mastered_concepts_count": 2,
        "average_retention_probability": 0.89,
        "recent_events": [],
    }
    monkeypatch.setattr(
        learning_memory_service,
        "get_historical_learning_summary",
        AsyncMock(return_value=mock_summary),
    )

    resp = client.get("/api/v1/memory/test_api_learner/summary")
    assert resp.status_code == 200
    assert resp.json()["overall_mastery"] == 0.88
    assert resp.json()["total_sessions"] == 2
