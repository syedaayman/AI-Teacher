from fastapi import APIRouter

from app.api.v1.adaptive import router as adaptive_router
from app.api.v1.assessment import router as assessment_router
from app.api.v1.concepts import router as concepts_router
from app.api.v1.health import router as health_router
from app.api.v1.learner_profile import router as learner_profile_router
from app.api.v1.lessons import router as lessons_router
from app.api.v1.materials import router as materials_router
from app.api.v1.memory import router as memory_router
from app.api.v1.rag import router as rag_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.video import router as video_router

api_v1_router = APIRouter()

# Register sub-routers
api_v1_router.include_router(health_router)
api_v1_router.include_router(materials_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(concepts_router)
api_v1_router.include_router(lessons_router)
api_v1_router.include_router(sessions_router)
api_v1_router.include_router(assessment_router)
api_v1_router.include_router(adaptive_router)
api_v1_router.include_router(learner_profile_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(video_router)

