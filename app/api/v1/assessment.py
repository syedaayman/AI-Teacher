from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.api import (
    AnswerEvaluationRequest,
    MisconceptionDetectionRequest,
    QuestionGenerationRequest,
)
from app.schemas.assessment import (
    AssessmentReport,
    EvaluationResult,
    FinalAssessmentPackage,
    FinalAssessmentRequest,
    FinalAssessmentSubmission,
    MisconceptionAnalysis,
    Question,
)
from app.services.answer_evaluator import answer_evaluator
from app.services.assessment_report_service import assessment_report_service
from app.services.misconception_detector import misconception_detector
from app.services.question_generator import question_generator

router = APIRouter(prefix="/assessment", tags=["Assessment"])


@router.post(
    "/generate-questions",
    response_model=List[Question],
    status_code=status.HTTP_200_OK,
    summary="Generate assessment questions for a concept",
)
async def generate_questions(req: QuestionGenerationRequest) -> List[Question]:
    """Generate batch of assessment questions (MCQ, Short Answer, Conceptual, Application)."""
    return await question_generator.generate_questions(
        concept=req.concept,
        question_types=[req.question_type],
        count=req.count,
        lesson_id=req.lesson_id,
    )


@router.post(
    "/evaluate-answer",
    response_model=EvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate learner answer",
)
async def evaluate_answer(req: AnswerEvaluationRequest) -> EvaluationResult:
    """Evaluate student submission deterministically (MCQ) or semantically (open-ended)."""
    return await answer_evaluator.evaluate_answer(
        question=req.question,
        student_answer=req.student_answer,
    )


@router.post(
    "/detect-misconceptions",
    response_model=MisconceptionAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Diagnose conceptual or prerequisite misconceptions",
)
async def detect_misconceptions(req: MisconceptionDetectionRequest) -> MisconceptionAnalysis:
    """Analyze learner answer and evaluation to diagnose active misconceptions."""
    return await misconception_detector.detect_misconceptions(
        question=req.question,
        student_answer=req.student_answer,
        evaluation_result=req.evaluation_result,
        concept=req.concept,
        concept_graph=req.concept_graph,
    )


# --------------------------------------------------------------------
# Final Assessment & Comprehensive Learning Report Endpoints
# --------------------------------------------------------------------

@router.post(
    "/final/generate",
    response_model=FinalAssessmentPackage,
    status_code=status.HTTP_201_CREATED,
    summary="Generate comprehensive final assessment package",
)
async def generate_final_assessment(
    req: FinalAssessmentRequest,
) -> FinalAssessmentPackage:
    """Generate multi-concept assessment questions spanning target curriculum concepts."""
    return await assessment_report_service.generate_assessment(req)


@router.post(
    "/final/evaluate",
    response_model=AssessmentReport,
    status_code=status.HTTP_200_OK,
    summary="Evaluate final assessment and generate diagnostic learning report",
)
async def evaluate_final_assessment(
    submission: FinalAssessmentSubmission,
    db: AsyncSession = Depends(get_db),
) -> AssessmentReport:
    """Evaluate exam answers, diagnose flaws, calculate letter grade, and produce multilingual report."""
    return await assessment_report_service.evaluate_assessment(
        submission=submission,
        db_session=db,
    )
