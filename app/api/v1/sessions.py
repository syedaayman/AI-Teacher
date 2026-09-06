"""
Teaching session endpoints orchestrating the continuous human-like teaching loop:
Understand -> Plan -> Explain -> Demonstrate -> Question -> Evaluate -> Adapt -> Continue.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import InvalidSessionStateError, TeacherSessionError
from app.schemas.session import (
    AdvanceStepRequest,
    LessonSessionState,
    SessionStatus,
    SessionStepResponse,
    StartSessionRequest,
    SubmitAnswerRequest,
    SwitchLanguageRequest,
)
from app.services.session_service import session_service
from app.services.teacher_agent import teacher_agent

router = APIRouter(prefix="/sessions", tags=["Teaching Sessions"])


@router.post(
    "/start",
    response_model=SessionStepResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an adaptive teaching session",
)
async def start_session(
    req: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionStepResponse:
    """Initialize an 8-step continuous teaching loop calibrated to time and depth budgets."""
    try:
        return await teacher_agent.start_teaching_session(req, db_session=db)
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start teaching session: {str(ex)}",
        )


@router.post(
    "/advance",
    response_model=SessionStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Advance to next instructional step (Explain -> Demonstrate -> Question)",
)
async def advance_step(
    req: AdvanceStepRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionStepResponse:
    """Transition from conceptual explanation to demonstration, or from demonstration to question."""
    try:
        return await teacher_agent.advance_step(req, db_session=db)
    except InvalidSessionStateError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ex))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@router.post(
    "/submit-answer",
    response_model=SessionStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit student answer to active question",
)
async def submit_answer(
    req: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionStepResponse:
    """Evaluate submitted answer, diagnose misconceptions, execute adaptive action, and advance."""
    try:
        return await teacher_agent.submit_answer(req, db_session=db)
    except InvalidSessionStateError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ex))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@router.post(
    "/switch-language",
    response_model=SessionStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Switch instructional language mid-session (English, Hindi, Hinglish)",
)
async def switch_language(
    req: SwitchLanguageRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionStepResponse:
    """Change session language, update learner preference in DB, and re-render delivery immediately."""
    try:
        return await teacher_agent.switch_session_language(
            session_id=req.session_id,
            new_language=req.language,
            db_session=db,
        )
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@router.get(
    "/{session_id}",
    response_model=LessonSessionState,
    status_code=status.HTTP_200_OK,
    summary="Retrieve active session state",
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> LessonSessionState:
    """Get full state of an ongoing or completed teaching session."""
    try:
        return await session_service.get_session(session_id, db_session=db)
    except TeacherSessionError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))


@router.post(
    "/{session_id}/end",
    response_model=LessonSessionState,
    status_code=status.HTTP_200_OK,
    summary="Conclude or abandon a teaching session",
)
async def end_session(
    session_id: str,
    final_status: SessionStatus = SessionStatus.COMPLETED,
    db: AsyncSession = Depends(get_db),
) -> LessonSessionState:
    """Mark session completed or abandoned and persist final log timestamp."""
    try:
        return await session_service.end_session(session_id, status=final_status, db_session=db)
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))
