import hashlib
import logging
import re
from typing import List, Optional

from app.core.exceptions import (
    AdaptiveEngineError,
    InvalidAdaptationDecisionError,
    InvalidDifficultyTransitionError,
    InvalidMasteryInputError,
    MissingConceptError,
)
from app.schemas.adaptive import (
    AdaptationAction,
    AdaptationDecision,
    ConceptMastery,
    MasteryLevel,
)
from app.schemas.assessment import (
    EvaluationResult,
    MisconceptionAnalysis,
)
from app.schemas.lesson import Concept, ConceptGraph, DifficultyLevel
from app.services.concept_service import concept_service
from app.services.mastery_engine import mastery_engine

logger = logging.getLogger(__name__)


class AdaptiveEngine:
    """Deterministic pedagogical decision engine determining next instructional actions."""

    def __init__(self, mastery_svc=None, concept_svc=None):
        self._mastery_engine = mastery_svc or mastery_engine
        self._concept_service = concept_svc or concept_service

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_decision_id(
        current_concept_id: str,
        action: str,
        target_concept_id: str,
        target_difficulty: str,
        mastery_score: float,
        learner_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Generate a deterministic SHA-256 adaptation decision ID."""
        if not current_concept_id or not action or not target_concept_id:
            raise InvalidAdaptationDecisionError("Cannot generate decision ID with missing parameters.")

        l_id = (learner_id or "anon").strip()
        s_id = (session_id or "none").strip()
        act = action.strip().lower()
        t_diff = target_difficulty.strip().lower()

        seed = f"{l_id}:{s_id}:{current_concept_id}:{act}:{target_concept_id}:{t_diff}:{mastery_score:.4f}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"adt_{digest}"

    # ----------------------------------------------------------------
    # Difficulty Transitions
    # ----------------------------------------------------------------

    @staticmethod
    def increase_difficulty(current: DifficultyLevel) -> DifficultyLevel:
        """Step up difficulty to next bracket. Raises InvalidDifficultyTransitionError if already ADVANCED."""
        if current == DifficultyLevel.BEGINNER:
            return DifficultyLevel.INTERMEDIATE
        elif current == DifficultyLevel.INTERMEDIATE:
            return DifficultyLevel.ADVANCED
        elif current == DifficultyLevel.ADVANCED:
            raise InvalidDifficultyTransitionError("Cannot increase difficulty beyond advanced.")
        else:
            raise InvalidDifficultyTransitionError(f"Unknown difficulty level: {current}")

    @staticmethod
    def decrease_difficulty(current: DifficultyLevel) -> DifficultyLevel:
        """Step down difficulty to previous bracket. Raises InvalidDifficultyTransitionError if already BEGINNER."""
        if current == DifficultyLevel.ADVANCED:
            return DifficultyLevel.INTERMEDIATE
        elif current == DifficultyLevel.INTERMEDIATE:
            return DifficultyLevel.BEGINNER
        elif current == DifficultyLevel.BEGINNER:
            raise InvalidDifficultyTransitionError("Cannot decrease difficulty below beginner.")
        else:
            raise InvalidDifficultyTransitionError(f"Unknown difficulty level: {current}")

    # ----------------------------------------------------------------
    # Core Decision Logic
    # ----------------------------------------------------------------

    def decide_next_action(
        self,
        current_concept_id: str,
        current_difficulty: DifficultyLevel,
        evaluation_result: EvaluationResult,
        concept_mastery: ConceptMastery,
        misconception_analysis: Optional[MisconceptionAnalysis] = None,
        concept_graph: Optional[ConceptGraph] = None,
        learner_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AdaptationDecision:
        """Evaluate assessment performance and return a deterministic, prioritized AdaptationDecision."""
        if not current_concept_id or not current_concept_id.strip():
            raise MissingConceptError("current_concept_id cannot be empty or None.")
        if not evaluation_result:
            raise AdaptiveEngineError("evaluation_result is required to make an adaptation decision.")
        if not concept_mastery:
            raise InvalidMasteryInputError("concept_mastery is required to make an adaptation decision.")

        score = evaluation_result.score
        mastery_score = concept_mastery.mastery_score
        mastery_level = concept_mastery.mastery_level

        # Extract active misconceptions with actionable confidence
        active_misconceptions = []
        if misconception_analysis and misconception_analysis.detected:
            for m in misconception_analysis.misconceptions:
                if m.confidence >= 0.70:
                    active_misconceptions.append(m)

        misc_ids = [m.misconception_id for m in active_misconceptions]
        prereq_ids = self._get_concept_prerequisites(current_concept_id, concept_graph)

        # ------------------------------------------------------------
        # PRIORITY 1: Prerequisite Misconception
        # ------------------------------------------------------------
        prereq_misconceptions = []
        for m in active_misconceptions:
            for aff_id in m.affected_concept_ids:
                if aff_id in prereq_ids and aff_id != current_concept_id:
                    prereq_misconceptions.append((aff_id, m))

        if prereq_misconceptions:
            # Deterministic selection of prerequisite (sort by ID)
            prereq_misconceptions.sort(key=lambda x: x[0])
            target_prereq_id, target_misc = prereq_misconceptions[0]

            reason = (
                f"Prerequisite concept '{target_prereq_id}' requires review because the learner "
                f"demonstrated a genuine prerequisite misconception."
            )
            evidence = [
                f"Current concept: {current_concept_id}",
                f"Diagnosed prerequisite misconception: {target_misc.description}",
                f"Prerequisite concept target: {target_prereq_id}",
                f"Evaluation score: {score:.2f}, Mastery score: {mastery_score:.2f}",
            ]
            action = AdaptationAction.REVIEW_PREREQUISITE
            target_concept_id = target_prereq_id
            target_difficulty = DifficultyLevel.BEGINNER

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # ------------------------------------------------------------
        # PRIORITY 2: Genuine Conceptual Misconception
        # ------------------------------------------------------------
        if active_misconceptions:
            primary_misc = active_misconceptions[0]
            reason = (
                f"Learner demonstrated an active conceptual misconception on '{current_concept_id}'. "
                f"Remediation is required before continuing."
            )
            evidence = [
                f"Current concept: {current_concept_id}",
                f"Active misconception: {primary_misc.description}",
                f"Severity: {primary_misc.severity.value}, Confidence: {primary_misc.confidence:.2f}",
                f"Evaluation score: {score:.2f}",
            ]
            action = AdaptationAction.REMEDIATE_MISCONCEPTION
            target_concept_id = current_concept_id
            target_difficulty = current_difficulty

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # ------------------------------------------------------------
        # PRIORITY 3: Repeated Failure
        # ------------------------------------------------------------
        is_repeated_failure = (
            concept_mastery.incorrect_attempts >= 2
            or (concept_mastery.attempts >= 2 and score < 0.25 and mastery_score < 0.35)
        )
        if is_repeated_failure:
            if current_difficulty in (DifficultyLevel.ADVANCED, DifficultyLevel.INTERMEDIATE):
                new_diff = self.decrease_difficulty(current_difficulty)
                reason = (
                    f"Learner has experienced repeated failures on concept '{current_concept_id}'. "
                    f"Stepping down difficulty from {current_difficulty.value} to {new_diff.value}."
                )
                evidence = [
                    f"Total attempts: {concept_mastery.attempts}, Incorrect: {concept_mastery.incorrect_attempts}",
                    f"Latest score: {score:.2f}, Cumulative mastery: {mastery_score:.2f}",
                    f"Previous difficulty: {current_difficulty.value} -> New difficulty: {new_diff.value}",
                ]
                action = AdaptationAction.DECREASE_DIFFICULTY
                target_concept_id = current_concept_id
                target_difficulty = new_diff
            else:
                # Already at beginner: reteach concept
                reason = (
                    f"Learner has experienced repeated failures at beginner level on '{current_concept_id}'. "
                    f"Reteaching foundational concept."
                )
                evidence = [
                    f"Total attempts: {concept_mastery.attempts}, Incorrect: {concept_mastery.incorrect_attempts}",
                    f"Latest score: {score:.2f}, Cumulative mastery: {mastery_score:.2f}",
                    "Difficulty is already at beginner level.",
                ]
                action = AdaptationAction.RETEACH_CONCEPT
                target_concept_id = current_concept_id
                target_difficulty = DifficultyLevel.BEGINNER

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # ------------------------------------------------------------
        # PRIORITY 4: Low Mastery / Incomplete Understanding
        # ------------------------------------------------------------
        if mastery_level in (MasteryLevel.NOT_STARTED, MasteryLevel.EMERGING) or score < 0.50:
            if concept_mastery.attempts >= 2 or score < 0.25:
                action = AdaptationAction.RETEACH_CONCEPT
                reason = (
                    f"Performance on concept '{current_concept_id}' shows low mastery. "
                    f"Reteaching core concepts."
                )
            else:
                action = AdaptationAction.RETRY_QUESTION
                reason = (
                    f"Initial attempt on concept '{current_concept_id}' shows emerging understanding. "
                    f"Retrying with another assessment question."
                )

            evidence = [
                f"Latest evaluation score: {score:.2f}",
                f"Cumulative mastery score: {mastery_score:.2f} ({mastery_level.value})",
                f"Total attempts on concept: {concept_mastery.attempts}",
            ]
            target_concept_id = current_concept_id
            target_difficulty = current_difficulty

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # ------------------------------------------------------------
        # PRIORITY 5: Partial Understanding
        # ------------------------------------------------------------
        if mastery_level == MasteryLevel.DEVELOPING or (0.50 <= score < 0.75):
            action = AdaptationAction.RETRY_QUESTION
            reason = (
                f"Learner demonstrates partial/developing understanding on '{current_concept_id}'. "
                f"Retrying with a reinforcement question."
            )
            evidence = [
                f"Latest evaluation score: {score:.2f}",
                f"Cumulative mastery: {mastery_score:.2f} ({mastery_level.value})",
                f"Partial attempts: {concept_mastery.partial_attempts}",
            ]
            target_concept_id = current_concept_id
            target_difficulty = current_difficulty

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # ------------------------------------------------------------
        # PRIORITY 6: Strong Performance / Advancement
        # ------------------------------------------------------------
        if score >= 0.75:
            if current_difficulty in (DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE):
                new_diff = self.increase_difficulty(current_difficulty)
                action = AdaptationAction.INCREASE_DIFFICULTY
                reason = (
                    f"Strong performance on '{current_concept_id}' at {current_difficulty.value} level. "
                    f"Increasing difficulty to {new_diff.value}."
                )
                evidence = [
                    f"Evaluation score: {score:.2f} (Correct)",
                    f"Cumulative mastery score: {mastery_score:.2f} ({mastery_level.value})",
                    f"Difficulty transition: {current_difficulty.value} -> {new_diff.value}",
                ]
                target_concept_id = current_concept_id
                target_difficulty = new_diff
            else:
                # ADVANCED with proficient / mastered
                next_c_id = self._find_next_concept(current_concept_id, concept_graph)
                target_concept_id = next_c_id if next_c_id else current_concept_id
                action = AdaptationAction.ADVANCE_CONCEPT
                reason = (
                    f"Learner has mastered concept '{current_concept_id}' at advanced level. "
                    f"Advancing to next concept '{target_concept_id}'."
                )
                evidence = [
                    f"Evaluation score: {score:.2f} at ADVANCED difficulty",
                    f"Cumulative mastery score: {mastery_score:.2f} ({mastery_level.value})",
                    f"Target advancement concept: {target_concept_id}",
                ]
                target_difficulty = DifficultyLevel.BEGINNER

            decision_id = self.generate_decision_id(
                current_concept_id=current_concept_id,
                action=action.value,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty.value,
                mastery_score=mastery_score,
                learner_id=learner_id,
                session_id=session_id,
            )
            return AdaptationDecision(
                decision_id=decision_id,
                learner_id=learner_id,
                session_id=session_id,
                current_concept_id=current_concept_id,
                action=action,
                target_concept_id=target_concept_id,
                target_difficulty=target_difficulty,
                reason=reason,
                evidence=evidence,
                mastery_score=mastery_score,
                misconception_ids=misc_ids,
                prerequisite_concept_ids=prereq_ids,
                confidence=round(concept_mastery.confidence, 4),
            )

        # Default fallback
        action = AdaptationAction.CONTINUE
        decision_id = self.generate_decision_id(
            current_concept_id=current_concept_id,
            action=action.value,
            target_concept_id=current_concept_id,
            target_difficulty=current_difficulty.value,
            mastery_score=mastery_score,
            learner_id=learner_id,
            session_id=session_id,
        )
        return AdaptationDecision(
            decision_id=decision_id,
            learner_id=learner_id,
            session_id=session_id,
            current_concept_id=current_concept_id,
            action=action,
            target_concept_id=current_concept_id,
            target_difficulty=current_difficulty,
            reason=f"Continuing instructional sequence for concept '{current_concept_id}'.",
            evidence=[f"Evaluation score: {score:.2f}", f"Mastery: {mastery_score:.2f}"],
            mastery_score=mastery_score,
            misconception_ids=misc_ids,
            prerequisite_concept_ids=prereq_ids,
            confidence=round(concept_mastery.confidence, 4),
        )

    # ----------------------------------------------------------------
    # Graph & Helper Utilities
    # ----------------------------------------------------------------

    def _get_concept_prerequisites(
        self,
        concept_id: str,
        concept_graph: Optional[ConceptGraph],
    ) -> List[str]:
        """Extract prerequisite concept IDs deterministically from ConceptGraph."""
        if not concept_graph or not concept_graph.concepts:
            return []

        for c in concept_graph.concepts:
            if c.concept_id == concept_id:
                return sorted(list(c.prerequisite_concept_ids))

        return []

    def _find_next_concept(
        self,
        current_concept_id: str,
        concept_graph: Optional[ConceptGraph],
    ) -> Optional[str]:
        """Find deterministic next concept in topological order from ConceptGraph."""
        if not concept_graph or not concept_graph.concepts:
            return None

        try:
            sorted_concepts = self._concept_service.topological_sort(concept_graph.concepts)
            c_ids = [c.concept_id for c in sorted_concepts]
            if current_concept_id in c_ids:
                curr_idx = c_ids.index(current_concept_id)
                if curr_idx + 1 < len(c_ids):
                    return c_ids[curr_idx + 1]
        except Exception as e:
            logger.warning(f"Could not compute topological sort for next concept: {e}")

        return None


# Singleton service instance
adaptive_engine = AdaptiveEngine()
