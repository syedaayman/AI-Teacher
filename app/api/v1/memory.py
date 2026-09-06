"""
Long-term learning memory and spaced repetition review queue API endpoints.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import LearnerNotFoundError
from app.schemas.adaptive import MemoryUpdateResult, ReviewQueue
from app.services.learning_memory_service import learning_memory_service

router = APIRouter(prefix="/memory", tags=["Learning Memory & Spaced Repetition"])


class RecordMemoryUpdateRequest(BaseModel):
    """Payload to record an assessment or practice interaction for spaced repetition."""
    concept_id: str = Field(description="Concept reviewed")
    score: float = Field(ge=0.0, le=1.0, description="Score achieved on the review attempt (0.0 to 1.0)")


@router.get(
    "/{learner_id}/queue",
    response_model=ReviewQueue,
    status_code=status.HTTP_200_OK,
    summary="Get prioritized spaced repetition review queue",
)
async def get_review_queue(
    learner_id: str,
    max_items: int = Query(default=10, ge=1, le=50, description="Max items to return"),
    retention_threshold: float = Query(default=0.85, ge=0.5, le=0.99, description="Target retention cutoff"),
    db: AsyncSession = Depends(get_db),
) -> ReviewQueue:
    """Retrieve ordered list of concepts due for spaced repetition review based on memory decay curves."""
    try:
        return await learning_memory_service.get_review_queue(
            learner_id=learner_id,
            db_session=db,
            max_items=max_items,
            retention_threshold=retention_threshold,
        )
    except LearnerNotFoundError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@router.post(
    "/{learner_id}/update",
    response_model=MemoryUpdateResult,
    status_code=status.HTTP_200_OK,
    summary="Record concept review score and update SM-2 parameters",
)
async def update_memory(
    learner_id: str,
    req: RecordMemoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryUpdateResult:
    """Update repetition count, scheduled interval, and easiness factor following a concept review."""
    try:
        return await learning_memory_service.update_concept_memory(
            learner_id=learner_id,
            concept_id=req.concept_id,
            score=req.score,
            db_session=db,
        )
    except LearnerNotFoundError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@router.get(
    "/{learner_id}/summary",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Longitudinal learning memory and session summary",
)
async def get_memory_summary(
    learner_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve historical learning analytics spanning sessions, attempts, and memory retention."""
    try:
        return await learning_memory_service.get_historical_learning_summary(
            learner_id=learner_id,
            db_session=db,
        )
    except LearnerNotFoundError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))
