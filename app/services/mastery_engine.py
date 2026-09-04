import logging
from typing import Optional

from app.core.exceptions import InvalidMasteryInputError
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.assessment import EvaluationResult

logger = logging.getLogger(__name__)

# Mastery level threshold boundaries
MASTERY_THRESHOLDS = (
    (0.90, MasteryLevel.MASTERED),
    (0.75, MasteryLevel.PROFICIENT),
    (0.50, MasteryLevel.DEVELOPING),
    (0.20, MasteryLevel.EMERGING),
    (0.00, MasteryLevel.NOT_STARTED),
)


class MasteryEngine:
    """Domain service for deterministic concept mastery calculation and attempt tracking."""

    @staticmethod
    def calculate_mastery_level(score: float) -> MasteryLevel:
        """Map a numeric score (0.0 to 1.0) to its canonical categorical MasteryLevel."""
        if score is None or not (0.0 <= score <= 1.0):
            raise InvalidMasteryInputError(f"Score must be between 0.0 and 1.0. Received: {score}")

        for threshold, level in MASTERY_THRESHOLDS:
            if score >= threshold:
                return level
        return MasteryLevel.NOT_STARTED

    @staticmethod
    def calculate_confidence(attempts: int, evaluation_confidence: float) -> float:
        """Calculate deterministic mastery confidence based on attempt depth and evaluation confidence.
        
        Formula:
            confidence = min(1.0, 0.4 * eval_conf + 0.6 * min(1.0, attempts / 3.0))
        - 1st attempt: caps around 0.60
        - 2nd attempt: caps around 0.80
        - 3+ attempts: reaches up to 1.00
        """
        eval_conf = max(0.0, min(1.0, evaluation_confidence))
        attempt_factor = min(1.0, max(0.0, attempts / 3.0))
        computed = 0.4 * eval_conf + 0.6 * attempt_factor
        return round(max(0.0, min(1.0, computed)), 4)

    def update_mastery(
        self,
        concept_id: str,
        evaluation_result: EvaluationResult,
        previous_mastery: Optional[ConceptMastery] = None,
    ) -> ConceptMastery:
        """Update concept mastery deterministically from an EvaluationResult."""
        if not concept_id or not concept_id.strip():
            raise InvalidMasteryInputError("concept_id cannot be empty or None.")
        if not evaluation_result:
            raise InvalidMasteryInputError("evaluation_result cannot be None.")

        current_score = evaluation_result.score
        if not (0.0 <= current_score <= 1.0):
            raise InvalidMasteryInputError(
                f"EvaluationResult score must be between 0.0 and 1.0. Received: {current_score}"
            )

        # 1. Calculate new mastery score
        if previous_mastery is None or previous_mastery.attempts == 0:
            # First attempt: use evaluation score directly
            new_score = current_score
            attempts = 1
            correct = 1 if current_score >= 0.75 else 0
            partial = 1 if 0.25 <= current_score < 0.75 else 0
            incorrect = 1 if current_score < 0.25 else 0
        else:
            # Subsequent attempts: apply weighted moving average (0.6 previous + 0.4 current)
            smoothed = 0.6 * previous_mastery.mastery_score + 0.4 * current_score
            new_score = round(max(0.0, min(1.0, smoothed)), 4)
            attempts = previous_mastery.attempts + 1

            correct = previous_mastery.correct_attempts + (1 if current_score >= 0.75 else 0)
            partial = previous_mastery.partial_attempts + (1 if 0.25 <= current_score < 0.75 else 0)
            incorrect = previous_mastery.incorrect_attempts + (1 if current_score < 0.25 else 0)

        # 2. Determine categorical mastery level
        mastery_level = self.calculate_mastery_level(new_score)

        # 3. Determine deterministic confidence
        eval_conf = evaluation_result.confidence if evaluation_result.confidence is not None else 1.0
        confidence = self.calculate_confidence(attempts, eval_conf)

        return ConceptMastery(
            concept_id=concept_id,
            mastery_score=new_score,
            mastery_level=mastery_level,
            confidence=confidence,
            attempts=attempts,
            correct_attempts=correct,
            incorrect_attempts=incorrect,
            partial_attempts=partial,
            last_score=current_score,
        )


# Singleton service instance
mastery_engine = MasteryEngine()
