from fastapi import APIRouter, status

from app.schemas.adaptive import AdaptationDecision, ConceptMastery
from app.schemas.api import AdaptiveDecisionRequest, MasteryUpdateRequest
from app.services.adaptive_engine import adaptive_engine
from app.services.mastery_engine import mastery_engine

router = APIRouter(prefix="/adaptive", tags=["Adaptive Engine"])


@router.post(
    "/mastery/update",
    response_model=ConceptMastery,
    status_code=status.HTTP_200_OK,
    summary="Update concept mastery deterministically",
)
def update_mastery(req: MasteryUpdateRequest) -> ConceptMastery:
    """Calculate updated concept mastery score and level from EvaluationResult."""
    return mastery_engine.update_mastery(
        concept_id=req.concept_id,
        evaluation_result=req.evaluation_result,
        previous_mastery=req.previous_mastery,
    )


@router.post(
    "/decide",
    response_model=AdaptationDecision,
    status_code=status.HTTP_200_OK,
    summary="Derive next pedagogical adaptation action",
)
def decide_action(req: AdaptiveDecisionRequest) -> AdaptationDecision:
    """Evaluate performance, mastery, prerequisites, and misconceptions to choose next action."""
    return adaptive_engine.decide_next_action(
        current_concept_id=req.current_concept_id,
        current_difficulty=req.current_difficulty,
        evaluation_result=req.evaluation_result,
        concept_mastery=req.concept_mastery,
        misconception_analysis=req.misconception_analysis,
        concept_graph=req.concept_graph,
        learner_id=req.learner_id,
        session_id=req.session_id,
    )
