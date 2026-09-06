import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.core.exceptions import LLMQuotaExceededError, LLMServiceError
from app.main import app
from app.schemas.assessment import Question, QuestionType
from app.schemas.lesson import Concept, DifficultyLevel
from app.services.question_generator import QuestionGenerator, question_generator


@pytest.fixture
def mock_failing_client():
    client = MagicMock()
    client.is_configured = True
    # Simulate an unhandled network error, 502 Bad Gateway, or quota exceeded
    client.generate_structured = AsyncMock(side_effect=LLMQuotaExceededError("Quota exceeded 429 / 502"))
    return client


@pytest.fixture
def sample_concept():
    return Concept(
        concept_id="cpt_recursion_01",
        name="Recursion",
        description="A programming technique where a function calls itself to solve smaller instances of a problem until reaching a base condition.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objectives=["Explain the difference between recursive steps and base conditions."],
    )


def test_fallback_questions_direct_call(sample_concept):
    """Test _generate_fallback_questions generates MCQ and short answer with correct schema fields."""
    q_gen = QuestionGenerator()
    
    # Test MCQ generation
    mcq_questions = q_gen._generate_fallback_questions(
        concept=sample_concept,
        question_types=[QuestionType.MCQ],
        count=2,
    )
    assert len(mcq_questions) == 2
    for q in mcq_questions:
        assert isinstance(q, Question)
        assert q.question_type == QuestionType.MCQ
        assert len(q.options) >= 2
        assert q.correct_answer_index is not None
        assert 0 <= q.correct_answer_index < len(q.options)
        assert q.correct_answer == q.options[q.correct_answer_index]
        assert len(q.explanation) > 0
        assert len(q.misconception_hints) > 0
        assert q.evaluation_rubric is not None
        # Must pass schema validation
        QuestionGenerator.validate_question(q)

    # Test Short Answer generation
    sa_questions = q_gen._generate_fallback_questions(
        concept=sample_concept,
        question_types=[QuestionType.SHORT_ANSWER],
        count=2,
    )
    assert len(sa_questions) == 2
    for q in sa_questions:
        assert isinstance(q, Question)
        assert q.question_type in [QuestionType.SHORT_ANSWER, QuestionType.CONCEPTUAL]
        assert q.options == []
        assert len(q.correct_answer) > 0
        assert len(q.explanation) > 0
        assert len(q.misconception_hints) > 0
        # Must pass schema validation
        QuestionGenerator.validate_question(q)


@pytest.mark.parametrize("diff", [DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE, DifficultyLevel.ADVANCED])
def test_fallback_questions_all_difficulties(diff):
    """Test that all difficulty levels dynamically generate appropriate questions."""
    c = Concept(
        concept_id=f"cpt_{diff.value}",
        name=f"Dynamic Topic {diff.value}",
        description=f"Description for {diff.value} topic.",
        difficulty=diff,
    )
    questions = QuestionGenerator._generate_fallback_questions(
        concept=c,
        question_types=[QuestionType.MCQ, QuestionType.SHORT_ANSWER],
        count=4,
    )
    assert len(questions) == 4
    for q in questions:
        assert q.difficulty == diff
        assert c.name in q.question_text or c.name in q.correct_answer or c.name in q.explanation
        QuestionGenerator.validate_question(q)


@pytest.mark.asyncio
async def test_generate_questions_quota_exhausted_fallback(sample_concept, mock_failing_client):
    """Test that when Gemini LLM throws LLMQuotaExceededError, fallback questions are returned without raising."""
    generator = QuestionGenerator(client=mock_failing_client)
    questions = await generator.generate_questions(
        concept=sample_concept,
        count=3,
        question_types=[QuestionType.MCQ, QuestionType.SHORT_ANSWER],
    )
    assert len(questions) == 3
    for q in questions:
        assert isinstance(q, Question)
        QuestionGenerator.validate_question(q)


@pytest.mark.asyncio
async def test_generate_questions_network_error_fallback(sample_concept):
    """Test that when Gemini LLM throws a generic network Exception/HTTP 502, fallback questions are returned."""
    client = MagicMock()
    client.generate_structured = AsyncMock(side_effect=Exception("HTTP 502 Bad Gateway: Upstream LLM unavailable"))
    generator = QuestionGenerator(client=client)

    questions = await generator.generate_questions(
        concept=sample_concept,
        count=2,
    )
    assert len(questions) == 2
    for q in questions:
        assert isinstance(q, Question)
        QuestionGenerator.validate_question(q)


@pytest.mark.asyncio
async def test_generate_question_singular_fallback(sample_concept, mock_failing_client):
    """Test that singular generate_question returns a single valid Question on failure."""
    generator = QuestionGenerator(client=mock_failing_client)
    q = await generator.generate_question(
        concept=sample_concept,
        question_type=QuestionType.MCQ,
    )
    assert isinstance(q, Question)
    assert q.question_type == QuestionType.MCQ
    assert len(q.options) >= 2
    QuestionGenerator.validate_question(q)


def test_api_assessment_generate_questions_endpoint_resilience(sample_concept):
    """Test that POST /api/v1/assessment/generate-questions returns 200 OK with valid questions even when LLM fails."""
    client = TestClient(app)

    # Monkeypatch the singleton question_generator._gemini_client to raise a 502
    mock_llm = MagicMock()
    mock_llm.generate_structured = AsyncMock(side_effect=Exception("502 Bad Gateway / Connection reset"))
    original_client = question_generator._gemini_client
    question_generator._gemini_client = mock_llm

    try:
        response = client.post(
            "/api/v1/assessment/generate-questions",
            json={
                "concept": sample_concept.model_dump(),
                "question_type": "mcq",
                "count": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for item in data:
            assert "question_id" in item
            assert item["question_type"] == "mcq"
            assert len(item["options"]) >= 2
            assert "correct_answer" in item
            assert "correct_answer_index" in item
            assert item["correct_answer_index"] is not None
            assert "explanation" in item
            assert "misconception_hints" in item
            assert len(item["misconception_hints"]) > 0
    finally:
        question_generator._gemini_client = original_client
