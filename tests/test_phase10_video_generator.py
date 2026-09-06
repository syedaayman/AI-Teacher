import pytest
from fastapi.testclient import TestClient

from app.api.v1.router import api_v1_router
from app.services.video_generator import VideoGeneratorService, video_generator_service
from fastapi import FastAPI

app = FastAPI()
app.include_router(api_v1_router, prefix="/api/v1")
client = TestClient(app)


def test_01_video_generator_provider_status():
    """Verify video provider status accurately reports local and external engines."""
    svc = VideoGeneratorService()
    status = svc.get_provider_status()
    assert "active_provider" in status
    assert len(status["providers"]) >= 3
    
    local_p = next(p for p in status["providers"] if p["id"] == "local_canvas_composer")
    assert local_p["status"] == "available"
    assert local_p["requires_api_key"] is False


def test_02_plan_lesson_video_scenes():
    """Verify plan_lesson_video_scenes builds sequenced progressive scenes."""
    svc = VideoGeneratorService()
    manifest = svc.plan_lesson_video_scenes(
        topic="Newton's Laws of Motion",
        concept_name="First Law: Inertia",
        delivery_content="An object remains at rest unless acted upon by an unbalanced force.\nThis means inertia resists changes in velocity.",
    )

    assert manifest.topic == "Newton's Laws of Motion"
    assert manifest.concept_name == "First Law: Inertia"
    assert len(manifest.scenes) == 6

    # Verify standard pedagogical progression (Intro -> Explanation -> Visual -> Demo -> Takeaway -> Question)
    scene_types = [s.scene_type for s in manifest.scenes]
    assert scene_types == ["intro", "explanation", "visual", "demonstration", "key_takeaway", "question"]

    assert manifest.total_duration_seconds > 20.0
    assert manifest.playable_format == "video/webm"


def test_03_video_api_endpoints():
    """Verify /api/v1/video/providers and /api/v1/video/plan-scenes endpoints."""
    # Test GET providers
    resp_prov = client.get("/api/v1/video/providers")
    assert resp_prov.status_code == 200
    data_prov = resp_prov.json()
    assert "providers" in data_prov

    # Test POST plan-scenes
    resp_plan = client.post(
        "/api/v1/video/plan-scenes",
        json={
            "topic": "Electromagnetism",
            "concept_name": "Faraday's Law",
            "delivery_content": "A changing magnetic flux induces an electromotive force.",
            "language": "english",
        },
    )
    assert resp_plan.status_code == 200
    data_plan = resp_plan.json()
    assert data_plan["concept_name"] == "Faraday's Law"
    assert len(data_plan["scenes"]) == 6


def test_04_synthesize_speech_audio_endpoint():
    """Verify /api/v1/video/synthesize-speech produces authentic audio/mpeg stream."""
    resp = client.post(
        "/api/v1/video/synthesize-speech",
        json={
            "text": "Photosynthesis converts solar light energy into chemical energy.",
            "language": "english",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] in ["audio/mpeg", "audio/wav"]
    # Verify non-empty, genuine audio stream bytes
    assert len(resp.content) > 1000


def test_05_configuration_check_and_fallback_to_local_canvas():
    """Verify structured configuration checks for HEYGEN_API_KEY and DID_API_KEY and fallback to local_canvas."""
    resp = client.get("/api/v1/video/configuration")
    assert resp.status_code == 200
    data = resp.json()
    assert "configuration_check" in data
    assert "HEYGEN_API_KEY" in data["configuration_check"]
    assert "DID_API_KEY" in data["configuration_check"]
    # When keys are missing from test environment, active provider must be local_canvas
    assert data["active_provider"] == "local_canvas"
    assert data["provider"] == "local_canvas"


def test_06_pre_rendered_audio_timing_cues():
    """Verify plan_lesson_video_scenes produces pre-rendered audio timing cues for TeacherStage."""
    svc = VideoGeneratorService()
    manifest = svc.plan_lesson_video_scenes(
        topic="Computer Science",
        concept_name="Binary Search",
        delivery_content="Binary search divides a sorted array in half at each step. This achieves logarithmic time complexity.",
    )
    assert manifest.provider == "local_canvas"
    assert len(manifest.timing_cues) > 0
    # Every cue has start_time, end_time, duration, text, and avatar_state
    for cue in manifest.timing_cues:
        assert cue.start_time >= 0.0
        assert cue.end_time > cue.start_time
        assert cue.duration > 0.0
        assert len(cue.text) > 0
        assert cue.avatar_state in ["IDLE", "SPEAKING", "THINKING", "LISTENING", "ENCOURAGING"]


