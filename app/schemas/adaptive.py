from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

from app.schemas.lesson import DifficultyLevel


class MasteryLevel(str, Enum):
    """Categorical representation of learner proficiency on a concept."""
    NOT_STARTED = "not_started"
    EMERGING = "emerging"
    DEVELOPING = "developing"
    PROFICIENT = "proficient"
    MASTERED = "mastered"


class AdaptationAction(str, Enum):
    """Deterministic pedagogical actions selected by the Adaptive Engine."""
    CONTINUE = "continue"
    INCREASE_DIFFICULTY = "increase_difficulty"
    DECREASE_DIFFICULTY = "decrease_difficulty"
    RETRY_QUESTION = "retry_question"
    RETEACH_CONCEPT = "reteach_concept"
    REMEDIATE_MISCONCEPTION = "remediate_misconception"
    REVIEW_PREREQUISITE = "review_prerequisite"
    ADVANCE_CONCEPT = "advance_concept"


class ConceptMastery(BaseModel):
    """Dynamic quantitative and categorical mastery status for a concept."""
    concept_id: str = Field(description="Unique concept ID")
    mastery_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Continuous mastery score between 0.0 and 1.0"
    )
    mastery_level: MasteryLevel = Field(description="Categorical mastery bracket")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the mastery estimation between 0.0 and 1.0"
    )
    attempts: int = Field(
        default=0,
        ge=0,
        description="Total number of assessment attempts on this concept"
    )
    correct_attempts: int = Field(
        default=0,
        ge=0,
        description="Count of fully correct submissions (score >= 0.75)"
    )
    incorrect_attempts: int = Field(
        default=0,
        ge=0,
        description="Count of incorrect submissions (score < 0.25)"
    )
    partial_attempts: int = Field(
        default=0,
        ge=0,
        description="Count of partially correct submissions (0.25 <= score < 0.75)"
    )
    last_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Score achieved on the most recent attempt"
    )

    @model_validator(mode="after")
    def validate_attempt_counts(self) -> "ConceptMastery":
        """Ensure specific attempt counts do not exceed total attempts."""
        total_sub_attempts = self.correct_attempts + self.incorrect_attempts + self.partial_attempts
        if total_sub_attempts > self.attempts:
            raise ValueError(
                f"Sum of correct ({self.correct_attempts}), incorrect ({self.incorrect_attempts}), "
                f"and partial ({self.partial_attempts}) attempts exceeds total attempts ({self.attempts})."
            )
        return self


class AdaptationDecision(BaseModel):
    """Deterministic, explainable next-step pedagogical instruction from the Adaptive Engine."""
    decision_id: str = Field(description="Deterministic SHA-256 unique decision identifier")
    learner_id: Optional[str] = Field(default=None, description="Optional tracking ID for the learner")
    session_id: Optional[str] = Field(default=None, description="Optional tracking ID for the learning session")
    current_concept_id: str = Field(description="Concept ID under assessment prior to decision")
    action: AdaptationAction = Field(description="Selected pedagogical adaptation action")
    target_concept_id: str = Field(description="Concept ID to target for the next instructional step")
    target_difficulty: DifficultyLevel = Field(description="Recommended difficulty for the next step")
    reason: str = Field(description="Human-readable explanation of why this action was chosen")
    evidence: List[str] = Field(
        default_factory=list,
        description="Concrete data points and rules that justified this decision"
    )
    mastery_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Concept mastery score at the time of decision"
    )
    misconception_ids: List[str] = Field(
        default_factory=list,
        description="IDs of active misconceptions that influenced the decision"
    )
    prerequisite_concept_ids: List[str] = Field(
        default_factory=list,
        description="Prerequisite concept IDs relevant to the decision"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score in the decision quality between 0.0 and 1.0"
    )
