from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.adaptive import ConceptMastery
from app.schemas.lesson import DifficultyLevel


class SupportedLanguage(str, Enum):
    """Supported instructional and communication languages for the learner."""
    ENGLISH = "english"
    HINDI = "hindi"
    HINGLISH = "hinglish"


class LearnerProfile(BaseModel):
    """Structured representation of learner identity, preferences, current concept mastery, and progress."""
    learner_id: str = Field(description="Unique identifier for the learner")
    name: Optional[str] = Field(default=None, description="Optional name/handle of the learner")
    preferred_language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Preferred instructional language"
    )
    learning_goal: Optional[str] = Field(
        default=None,
        description="Stated learning objective or curriculum goal"
    )
    preferred_difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Learner's preferred starting difficulty baseline"
    )
    concept_masteries: Dict[str, ConceptMastery] = Field(
        default_factory=dict,
        description="Map of concept_id to current ConceptMastery state"
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Concept IDs where learner demonstrates proficient or mastered competence"
    )
    weak_areas: List[str] = Field(
        default_factory=list,
        description="Concept IDs where learner demonstrates not_started or emerging competence"
    )
    mastered_concepts: List[str] = Field(
        default_factory=list,
        description="Concept IDs where mastery_level == MASTERED"
    )
    active_concepts: List[str] = Field(
        default_factory=list,
        description="Concept IDs currently under study (EMERGING or DEVELOPING)"
    )
    completed_lessons: List[str] = Field(
        default_factory=list,
        description="List of completed lesson IDs (unique and deduplicated)"
    )
    total_lessons: int = Field(
        default=0,
        ge=0,
        description="Total number of lessons in current curriculum"
    )
    assessment_count: int = Field(
        default=0,
        ge=0,
        description="Total number of assessments completed across all sessions"
    )
    average_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Running average score across all completed assessments"
    )
    overall_mastery: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Deterministic average mastery score across all assessed concepts"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the profile was initialized"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the profile was last modified"
    )

    @field_validator("learner_id")
    @classmethod
    def validate_learner_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("learner_id cannot be empty or whitespace.")
        return v.strip()

    @field_validator("completed_lessons")
    @classmethod
    def validate_completed_lessons_unique(cls, v: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for item in v:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped
