from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from app.schemas.api import LessonPlanRequest, SevenDayPlanRequest
from app.schemas.lesson import Syllabus
from app.services.concept_service import concept_service
from app.services.learner_profile import learner_profile_service
from app.services.lesson_planner import lesson_planner
from app.services.time_adaptive_planner import time_adaptive_planner

router = APIRouter(prefix="/lessons", tags=["Lessons"])


@router.post(
    "/plan",
    response_model=Syllabus,
    status_code=status.HTTP_200_OK,
    summary="Generate sequenced pedagogical syllabus",
)
async def plan_lessons(req: LessonPlanRequest) -> Syllabus:
    """Generate structured course syllabus from grounded material or topic."""
    if req.document:
        return await lesson_planner.generate_syllabus_from_material(
            document=req.document,
            title=req.title,
        )
    elif req.topic and req.topic.strip():
        return await lesson_planner.generate_syllabus_from_topic(
            topic=req.topic.strip(),
            title=req.title,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'topic' or 'document' must be provided for lesson planning.",
        )


@router.post(
    "/seven-day-plan",
    status_code=status.HTTP_200_OK,
    summary="Generate personalized 7-day learning and revision schedule",
)
async def generate_seven_day_plan(req: SevenDayPlanRequest) -> Dict[str, Any]:
    """Generate a personalized multi-day curriculum and spaced repetition schedule."""
    topic_title = (req.topic or "Curriculum").strip()
    
    # 1. Extract concepts
    if req.document:
        concepts = await concept_service.extract_concepts_from_material(req.document)
    elif req.topic and req.topic.strip():
        concepts = await concept_service.extract_concepts_from_topic(req.topic.strip())
    else:
        concepts = await concept_service.extract_concepts_from_topic("Foundational Principles")

    # 2. Build graph
    concept_graph = concept_service.build_concept_graph(concepts)

    # 3. Retrieve learner profile if provided
    profile = None
    if req.learner_id:
        try:
            profile = learner_profile_service.get_profile(req.learner_id)
        except Exception:
            profile = None

    # 4. Generate schedule
    return time_adaptive_planner.generate_seven_day_plan(
        concept_graph=concept_graph,
        topic=topic_title,
        daily_minutes=req.daily_minutes,
        learner_profile=profile,
    )

