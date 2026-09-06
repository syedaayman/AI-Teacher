from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.api import (
    CreateProfileRequest,
    RecordAssessmentRequest,
    RecordLessonRequest,
    UpdateMasteryRequest,
    UpdatePreferencesRequest,
)
from app.schemas.learner import LearnerProfile
from app.services.learner_profile import learner_profile_service

router = APIRouter(prefix="/learner-profile", tags=["Learner Profile"])


@router.post(
    "/create",
    response_model=LearnerProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Create new learner profile",
)
async def create_profile(
    req: CreateProfileRequest,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Initialize a new learner profile persisted to database."""
    return await learner_profile_service.create_profile_db(
        session=db,
        learner_id=req.learner_id,
        name=req.name,
        preferred_language=req.preferred_language,
        learning_goal=req.learning_goal,
        preferred_difficulty=req.preferred_difficulty,
        total_lessons=req.total_lessons,
    )


@router.get(
    "/{learner_id}",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Get learner profile by ID",
)
async def get_profile(
    learner_id: str,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Retrieve learner profile from database or cache."""
    return await learner_profile_service.get_profile_db(session=db, learner_id=learner_id)


@router.post(
    "/update-preferences",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Update learner preferences and goal",
)
async def update_preferences(
    req: UpdatePreferencesRequest,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Update preferred language, difficulty, or learning goal in database."""
    return await learner_profile_service.update_preferences_db(
        session=db,
        learner_id=req.learner_id,
        preferred_language=req.preferred_language,
        preferred_difficulty=req.preferred_difficulty,
        learning_goal=req.learning_goal,
    )


@router.post(
    "/update-mastery",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Update learner concept mastery and recompute summary",
)
async def update_mastery(
    req: UpdateMasteryRequest,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Incorporate ConceptMastery into database and update aggregate metrics."""
    return await learner_profile_service.update_mastery_db(
        session=db,
        learner_id=req.learner_id,
        concept_mastery=req.concept_mastery,
    )


@router.post(
    "/record-lesson",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Record completed lesson",
)
async def record_lesson(
    req: RecordLessonRequest,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Record completed lesson ID in database."""
    return await learner_profile_service.record_lesson_completion_db(
        session=db,
        learner_id=req.learner_id,
        lesson_id=req.lesson_id,
    )


@router.post(
    "/record-assessment",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Record assessment score and increment running average",
)
async def record_assessment(
    req: RecordAssessmentRequest,
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """Record assessment score and persist running average to database."""
    return await learner_profile_service.record_assessment_result_db(
        session=db,
        learner_id=req.learner_id,
        score=req.score,
    )

