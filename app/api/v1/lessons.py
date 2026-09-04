from fastapi import APIRouter, HTTPException, status

from app.schemas.api import LessonPlanRequest
from app.schemas.lesson import Syllabus
from app.services.lesson_planner import lesson_planner

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
