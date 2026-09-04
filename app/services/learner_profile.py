from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from app.core.exceptions import (
    InvalidLearnerProfileError,
    InvalidProfileUpdateError,
    LearnerNotFoundError,
)
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.learner import LearnerProfile, SupportedLanguage
from app.schemas.lesson import DifficultyLevel

logger = logging.getLogger(__name__)


class LearnerProfileService:
    """Domain service managing structured learner identity, preferences, mastery state, and progress."""

    def __init__(self):
        self._profiles: Dict[str, LearnerProfile] = {}

    def reset_store(self) -> None:
        """Clear the in-memory profile store (useful for clean test execution)."""
        self._profiles.clear()

    def create_profile(
        self,
        learner_id: str,
        name: Optional[str] = None,
        preferred_language: SupportedLanguage = SupportedLanguage.ENGLISH,
        learning_goal: Optional[str] = None,
        preferred_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        total_lessons: int = 0,
    ) -> LearnerProfile:
        """Initialize and store a new deterministic LearnerProfile."""
        if not learner_id or not learner_id.strip():
            raise InvalidLearnerProfileError("learner_id cannot be empty or whitespace.")

        clean_id = learner_id.strip()

        # Validate enums
        if not isinstance(preferred_language, SupportedLanguage):
            try:
                preferred_language = SupportedLanguage(preferred_language)
            except ValueError:
                raise InvalidLearnerProfileError(f"Unsupported language: {preferred_language}")

        if not isinstance(preferred_difficulty, DifficultyLevel):
            try:
                preferred_difficulty = DifficultyLevel(preferred_difficulty)
            except ValueError:
                raise InvalidLearnerProfileError(f"Invalid difficulty level: {preferred_difficulty}")

        if total_lessons < 0:
            raise InvalidLearnerProfileError(f"total_lessons cannot be negative: {total_lessons}")

        now = datetime.now(timezone.utc)
        profile = LearnerProfile(
            learner_id=clean_id,
            name=name.strip() if name else None,
            preferred_language=preferred_language,
            learning_goal=learning_goal.strip() if learning_goal else None,
            preferred_difficulty=preferred_difficulty,
            total_lessons=total_lessons,
            created_at=now,
            updated_at=now,
        )

        self._profiles[clean_id] = profile
        logger.info(f"Created learner profile for ID: {clean_id}")
        return profile

    def get_profile(self, learner_id: str) -> LearnerProfile:
        """Retrieve an existing learner profile by learner_id."""
        if not learner_id or not learner_id.strip():
            raise InvalidLearnerProfileError("learner_id cannot be empty or whitespace.")

        clean_id = learner_id.strip()
        if clean_id not in self._profiles:
            raise LearnerNotFoundError(f"Learner profile not found for ID '{clean_id}'.")

        return self._profiles[clean_id]

    def update_preferences(
        self,
        learner_id: str,
        preferred_language: Optional[SupportedLanguage] = None,
        preferred_difficulty: Optional[DifficultyLevel] = None,
        learning_goal: Optional[str] = None,
    ) -> LearnerProfile:
        """Update learner instructional preferences deterministically."""
        profile = self.get_profile(learner_id)

        if preferred_language is not None:
            if not isinstance(preferred_language, SupportedLanguage):
                try:
                    preferred_language = SupportedLanguage(preferred_language)
                except ValueError:
                    raise InvalidProfileUpdateError(f"Unsupported language: {preferred_language}")
            profile.preferred_language = preferred_language

        if preferred_difficulty is not None:
            if not isinstance(preferred_difficulty, DifficultyLevel):
                try:
                    preferred_difficulty = DifficultyLevel(preferred_difficulty)
                except ValueError:
                    raise InvalidProfileUpdateError(f"Invalid difficulty level: {preferred_difficulty}")
            profile.preferred_difficulty = preferred_difficulty

        if learning_goal is not None:
            profile.learning_goal = learning_goal.strip() if learning_goal else None

        profile.updated_at = datetime.now(timezone.utc)
        return profile

    def update_learning_goal(self, learner_id: str, learning_goal: str) -> LearnerProfile:
        """Update stated learning curriculum goal."""
        return self.update_preferences(learner_id, learning_goal=learning_goal)

    def update_mastery(
        self,
        learner_id: str,
        concept_mastery: ConceptMastery,
    ) -> LearnerProfile:
        """Incorporate new or updated ConceptMastery and recompute aggregate metrics."""
        if not concept_mastery:
            raise InvalidProfileUpdateError("concept_mastery cannot be None.")

        profile = self.get_profile(learner_id)
        profile.concept_masteries[concept_mastery.concept_id] = concept_mastery
        return self.recalculate_summary(profile)

    def record_lesson_completion(self, learner_id: str, lesson_id: str) -> LearnerProfile:
        """Record completed lesson uniquely and increment progress."""
        if not lesson_id or not lesson_id.strip():
            raise InvalidProfileUpdateError("lesson_id cannot be empty or whitespace.")

        clean_lesson_id = lesson_id.strip()
        profile = self.get_profile(learner_id)

        if clean_lesson_id not in profile.completed_lessons:
            profile.completed_lessons.append(clean_lesson_id)
            profile.updated_at = datetime.now(timezone.utc)

        return profile

    def record_assessment_result(self, learner_id: str, score: float) -> LearnerProfile:
        """Update assessment count and compute incremental running average score."""
        if score is None or not (0.0 <= score <= 1.0):
            raise InvalidProfileUpdateError(f"Assessment score must be between 0.0 and 1.0. Received: {score}")

        profile = self.get_profile(learner_id)
        new_count = profile.assessment_count + 1
        new_avg = (profile.average_score * profile.assessment_count + score) / new_count

        profile.assessment_count = new_count
        profile.average_score = round(max(0.0, min(1.0, new_avg)), 4)
        profile.updated_at = datetime.now(timezone.utc)
        return profile

    def recalculate_summary(self, profile: LearnerProfile) -> LearnerProfile:
        """Recalculate overall mastery, strengths, weak areas, and active concepts deterministically."""
        masteries = list(profile.concept_masteries.values())

        if not masteries:
            profile.overall_mastery = 0.0
            profile.strengths = []
            profile.weak_areas = []
            profile.mastered_concepts = []
            profile.active_concepts = []
        else:
            # Overall mastery is the deterministic mean of all assessed concept masteries
            mean_mastery = sum(m.mastery_score for m in masteries) / len(masteries)
            profile.overall_mastery = round(max(0.0, min(1.0, mean_mastery)), 4)

            # Strengths: PROFICIENT or MASTERED (deterministic sort)
            profile.strengths = sorted([
                m.concept_id for m in masteries
                if m.mastery_level in (MasteryLevel.PROFICIENT, MasteryLevel.MASTERED)
            ])

            # Weak areas: NOT_STARTED or EMERGING (deterministic sort)
            profile.weak_areas = sorted([
                m.concept_id for m in masteries
                if m.mastery_level in (MasteryLevel.NOT_STARTED, MasteryLevel.EMERGING)
            ])

            # Mastered concepts
            profile.mastered_concepts = sorted([
                m.concept_id for m in masteries
                if m.mastery_level == MasteryLevel.MASTERED
            ])

            # Active concepts: EMERGING or DEVELOPING
            profile.active_concepts = sorted([
                m.concept_id for m in masteries
                if m.mastery_level in (MasteryLevel.EMERGING, MasteryLevel.DEVELOPING)
            ])

        profile.updated_at = datetime.now(timezone.utc)
        return profile


# Singleton service instance
learner_profile_service = LearnerProfileService()
