from typing import List
from fastapi import APIRouter, status

from app.schemas.api import (
    AnswerEvaluationRequest,
    MisconceptionDetectionRequest,
    QuestionGenerationRequest,
)
from app.schemas.assessment import EvaluationResult, MisconceptionAnalysis, Question
from app.services.answer_evaluator import answer_evaluator
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
    return await question_generator.generate_question_batch(
        concept=req.concept,
        question_type=req.question_type,
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
