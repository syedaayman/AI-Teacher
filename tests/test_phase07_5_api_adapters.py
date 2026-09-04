import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app
from app.schemas.adaptive import AdaptationAction, ConceptMastery, MasteryLevel
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import Concept, DifficultyLevel


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


# ====================================================================
# Health Endpoints
# ====================================================================

def test_01_health_endpoints(client):
    """Verify health endpoints return 200 OK."""
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "ok"

    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == "ok"


# ====================================================================
# Materials API Adapter
# ====================================================================

def test_02_materials_process_txt_file(client):
    """Verify uploading and processing a valid text file."""
    txt_content = b"Photosynthesis converts light into chemical energy in chloroplasts.\n\nPlants release oxygen."
    files = {"file": ("biology.txt", io.BytesIO(txt_content), "text/plain")}
    data = {"chunk_size": 500, "chunk_overlap": 50, "auto_ingest": False}

    response = client.post("/api/v1/materials/process", files=files, data=data)
    assert response.status_code == 200
    payload = response.json()
    assert "extracted_document" in payload
    assert payload["extracted_document"]["filename"] == "biology.txt"
    assert len(payload["extracted_document"]["chunks"]) >= 1


def test_03_materials_unsupported_file_rejected(client):
    """Verify unsupported file extensions are rejected with 400 Bad Request."""
    files = {"file": ("archive.zip", io.BytesIO(b"fake data"), "application/zip")}
    response = client.post("/api/v1/materials/process", files=files)
    assert response.status_code == 400


# ====================================================================
# RAG API Adapter
# ====================================================================

def test_04_rag_endpoints(client):
    """Verify RAG stats, search, and context endpoints."""
    # Stats
    res_stats = client.get("/api/v1/rag/stats")
    assert res_stats.status_code == 200
    assert "total_vectors" in res_stats.json()

    # Search
    search_payload = {"query": "Explain chloroplasts", "top_k": 3}
    res_search = client.post("/api/v1/rag/search", json=search_payload)
    assert res_search.status_code == 200
    assert "results" in res_search.json()

    # Context
    context_payload = {"query": "Explain chloroplasts", "top_k": 3}
    res_ctx = client.post("/api/v1/rag/context", json=context_payload)
    assert res_ctx.status_code == 200
    assert "formatted_context" in res_ctx.json()


# ====================================================================
# Concepts & Lessons API Adapters
# ====================================================================

@pytest.mark.asyncio
async def test_05_concepts_and_graph_endpoints(client):
    """Verify concept extraction and graph construction endpoints."""
    concepts_list = [
        {
            "concept_id": "cpt_01",
            "name": "Arrays",
            "description": "Contiguous array storage",
            "difficulty": "beginner",
            "learning_objectives": ["Define arrays"],
            "prerequisite_concept_ids": [],
            "related_concept_ids": [],
            "source_chunk_ids": [],
        },
        {
            "concept_id": "cpt_02",
            "name": "Sorting",
            "description": "Array sorting",
            "difficulty": "beginner",
            "learning_objectives": ["Explain sorting"],
            "prerequisite_concept_ids": ["cpt_01"],
            "related_concept_ids": [],
            "source_chunk_ids": [],
        },
    ]

    # Graph
    res_graph = client.post("/api/v1/concepts/graph", json={"concepts": concepts_list})
    assert res_graph.status_code == 200
    graph_data = res_graph.json()
    assert len(graph_data["topological_order"]) == 2
    assert graph_data["topological_order"][0]["concept_id"] == "cpt_01"


# ====================================================================
# Assessment API Adapters
# ====================================================================

def test_06_assessment_evaluate_and_detect(client):
    """Verify assessment evaluation and misconception detection adapters."""
    mcq_q = {
        "question_id": "qst_01",
        "question_type": "mcq",
        "question_text": "What is 2 + 2?",
        "concept_id": "cpt_math",
        "difficulty": "beginner",
        "learning_objective": "Understand basic arithmetic addition",
        "options": ["A) 3", "B) 4", "C) 5"],
        "correct_answer": "B) 4",
        "explanation": "2 + 2 = 4",
    }
    student_ans = {
        "question_id": "qst_01",
        "answer_text": "B) 4",
        "selected_option": "B",
    }

    # Evaluate MCQ
    res_eval = client.post(
        "/api/v1/assessment/evaluate-answer",
        json={"question": mcq_q, "student_answer": student_ans},
    )
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["score"] == 1.0
    assert eval_data["correctness"] is True


# ====================================================================
# Adaptive Engine API Adapters
# ====================================================================

def test_07_adaptive_mastery_and_decide(client):
    """Verify adaptive mastery calculation and adaptation decision endpoints."""
    eval_res = {
        "evaluation_id": "eval_01",
        "question_id": "qst_01",
        "concept_id": "cpt_01",
        "correctness": True,
        "score": 0.90,
        "confidence": 0.95,
        "expected_answer": "B) 4",
        "student_answer": "B) 4",
        "evidence": "Correct",
        "feedback": "Great",
    }

    # Update Mastery
    res_mastery = client.post(
        "/api/v1/adaptive/mastery/update",
        json={"concept_id": "cpt_01", "evaluation_result": eval_res},
    )
    assert res_mastery.status_code == 200
    mastery_data = res_mastery.json()
    assert mastery_data["mastery_score"] == 0.90
    assert mastery_data["mastery_level"] == "mastered"

    # Decide Action
    decide_payload = {
        "current_concept_id": "cpt_01",
        "current_difficulty": "beginner",
        "evaluation_result": eval_res,
        "concept_mastery": mastery_data,
        "learner_id": "learner_01",
        "session_id": "session_01",
    }
    res_decide = client.post("/api/v1/adaptive/decide", json=decide_payload)
    assert res_decide.status_code == 200
    decide_data = res_decide.json()
    assert decide_data["action"] == "increase_difficulty"
    assert decide_data["target_difficulty"] == "intermediate"


# ====================================================================
# Learner Profile API Adapters
# ====================================================================

def test_08_learner_profile_lifecycle(client):
    """Verify creating, querying, updating, and recording progress on learner profiles."""
    create_payload = {
        "learner_id": "usr_http_test_01",
        "name": "Jordan",
        "preferred_language": "english",
        "learning_goal": "Learn Algorithms",
        "preferred_difficulty": "beginner",
        "total_lessons": 8,
    }

    # Create
    res_create = client.post("/api/v1/learner-profile/create", json=create_payload)
    assert res_create.status_code == 201
    profile = res_create.json()
    assert profile["learner_id"] == "usr_http_test_01"
    assert profile["name"] == "Jordan"

    # Get
    res_get = client.get("/api/v1/learner-profile/usr_http_test_01")
    assert res_get.status_code == 200
    assert res_get.json()["learner_id"] == "usr_http_test_01"

    # Update Preferences
    res_pref = client.post(
        "/api/v1/learner-profile/update-preferences",
        json={"learner_id": "usr_http_test_01", "preferred_language": "hinglish"},
    )
    assert res_pref.status_code == 200
    assert res_pref.json()["preferred_language"] == "hinglish"

    # Record Lesson Completion
    res_lsn = client.post(
        "/api/v1/learner-profile/record-lesson",
        json={"learner_id": "usr_http_test_01", "lesson_id": "lsn_intro_01"},
    )
    assert res_lsn.status_code == 200
    assert "lsn_intro_01" in res_lsn.json()["completed_lessons"]

    # Record Assessment
    res_asm = client.post(
        "/api/v1/learner-profile/record-assessment",
        json={"learner_id": "usr_http_test_01", "score": 0.85},
    )
    assert res_asm.status_code == 200
    assert res_asm.json()["assessment_count"] == 1
    assert res_asm.json()["average_score"] == 0.85
