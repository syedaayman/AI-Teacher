from fastapi import APIRouter, status

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
def create_profile(req: CreateProfileRequest) -> LearnerProfile:
    """Initialize a new learner profile."""
    return learner_profile_service.create_profile(
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
def get_profile(learner_id: str) -> LearnerProfile:
    """Retrieve learner profile."""
    return learner_profile_service.get_profile(learner_id)


@router.post(
    "/update-preferences",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Update learner preferences and goal",
)
def update_preferences(req: UpdatePreferencesRequest) -> LearnerProfile:
    """Update preferred language, difficulty, or learning goal."""
    return learner_profile_service.update_preferences(
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
def update_mastery(req: UpdateMasteryRequest) -> LearnerProfile:
    """Incorporate ConceptMastery into profile and update aggregate metrics."""
    return learner_profile_service.update_mastery(
        learner_id=req.learner_id,
        concept_mastery=req.concept_mastery,
    )


@router.post(
    "/record-lesson",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Record completed lesson",
)
def record_lesson(req: RecordLessonRequest) -> LearnerProfile:
    """Record completed lesson ID."""
    return learner_profile_service.record_lesson_completion(
        learner_id=req.learner_id,
        lesson_id=req.lesson_id,
    )


@router.post(
    "/record-assessment",
    response_model=LearnerProfile,
    status_code=status.HTTP_200_OK,
    summary="Record assessment score and increment running average",
)
def record_assessment(req: RecordAssessmentRequest) -> LearnerProfile:
    """Record assessment score."""
    return learner_profile_service.record_assessment_result(
        learner_id=req.learner_id,
        score=req.score,
    )
