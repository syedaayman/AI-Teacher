from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    """Canonical pedagogical difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ConceptRelationshipType(str, Enum):
    """Semantic relationship types between concepts."""
    PREREQUISITE = "prerequisite"
    RELATED = "related"


class ConceptRelationship(BaseModel):
    """A directed semantic relationship between two concepts."""
    source_concept_id: str = Field(description="Originating concept ID (prerequisite concept or primary node)")
    target_concept_id: str = Field(description="Target concept ID (dependent concept or related node)")
    relationship_type: ConceptRelationshipType = Field(
        default=ConceptRelationshipType.PREREQUISITE,
        description="Type of relationship (prerequisite, related)"
    )


class Concept(BaseModel):
    """Canonical pedagogical concept extracted from learning material or topic."""
    concept_id: str = Field(description="Deterministic SHA-256 unique identifier")
    name: str = Field(description="Normalized academic concept name")
    description: str = Field(description="Clear pedagogical description and conceptual scope")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Estimated pedagogical difficulty level"
    )
    learning_objectives: List[str] = Field(
        default_factory=list,
        description="Measurable action-oriented learning objectives (define, explain, apply, analyze, etc.)"
    )
    prerequisite_concept_ids: List[str] = Field(
        default_factory=list,
        description="IDs of prerequisite concepts that should be understood prior to this concept"
    )
    related_concept_ids: List[str] = Field(
        default_factory=list,
        description="IDs of conceptually related or complementary concepts"
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="IDs of source document chunks grounding this concept"
    )
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved source document metadata and attribution"
    )


class ConceptGraph(BaseModel):
    """Pure data model representing a graph of concepts and their relationships."""
    concepts: List[Concept] = Field(
        default_factory=list,
        description="List of all concepts in the graph"
    )
    relationships: List[ConceptRelationship] = Field(
        default_factory=list,
        description="Directed relationships between concepts"
    )


class Lesson(BaseModel):
    """A pedagogically coherent grouping of concepts structured for instructional delivery."""
    lesson_id: str = Field(description="Deterministic SHA-256 unique lesson identifier")
    title: str = Field(description="Concise, descriptive lesson title")
    description: str = Field(description="Pedagogical summary of what this lesson covers")
    concept_ids: List[str] = Field(
        default_factory=list,
        description="List of concept IDs included in this lesson"
    )
    learning_objectives: List[str] = Field(
        default_factory=list,
        description="Aggregated measurable learning objectives for this lesson"
    )
    prerequisite_lesson_ids: List[str] = Field(
        default_factory=list,
        description="IDs of preceding lessons that must be completed prior to this lesson"
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Aggregated pedagogical difficulty level of the lesson"
    )
    estimated_duration_minutes: int = Field(
        default=30,
        description="Estimated instructional duration in minutes (e.g., 15 to 60)"
    )
    sequence_index: int = Field(
        default=0,
        description="0-based sequence index respecting pedagogical prerequisite ordering"
    )
    source_material_ids: List[str] = Field(
        default_factory=list,
        description="IDs of source materials referenced by this lesson"
    )


class Syllabus(BaseModel):
    """Comprehensive course syllabus containing concepts, lessons, and sequence structure."""
    syllabus_id: str = Field(description="Deterministic SHA-256 unique syllabus identifier")
    title: str = Field(description="Syllabus course title")
    description: str = Field(description="High-level pedagogical description of the syllabus")
    concepts: List[Concept] = Field(
        default_factory=list,
        description="All extracted and normalized concepts"
    )
    lessons: List[Lesson] = Field(
        default_factory=list,
        description="Sequenced list of lessons"
    )
    lesson_ids: List[str] = Field(
        default_factory=list,
        description="Ordered list of lesson IDs matching the sequence"
    )
    source_material_ids: List[str] = Field(
        default_factory=list,
        description="IDs of source materials used to construct this syllabus"
    )
    is_grounded: bool = Field(
        description="True if derived directly from uploaded source material chunks; False if topic_only"
    )
    generation_mode: Literal["material_grounded", "topic_only"] = Field(
        description="Operational mode used to generate this syllabus"
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of syllabus generation"
    )


# ====================================================================
# Intermediate Pydantic Schemas for Structured LLM Interaction
# ====================================================================

class RawExtractedConcept(BaseModel):
    """Semantic payload extracted by LLM prior to deterministic ID and graph resolution."""
    name: str = Field(description="Academic name of the concept")
    description: str = Field(description="Pedagogical description of the concept")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Pedagogical difficulty level"
    )
    learning_objectives: List[str] = Field(
        default_factory=list,
        description="Measurable learning objectives (Bloom's taxonomy verbs)"
    )
    prerequisite_concept_names: List[str] = Field(
        default_factory=list,
        description="Names of other concepts in the material that are prerequisites"
    )
    related_concept_names: List[str] = Field(
        default_factory=list,
        description="Names of other concepts in the material that are related"
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Specific source chunk IDs from which this concept was extracted"
    )


class RawConceptExtractionResponse(BaseModel):
    """Structured LLM response container for concept extraction."""
    concepts: List[RawExtractedConcept] = Field(
        default_factory=list,
        description="List of extracted concepts"
    )


class RawLessonGrouping(BaseModel):
    """Semantic lesson grouping proposal from LLM."""
    title: str = Field(description="Title of the lesson")
    description: str = Field(description="Description of what is taught in this lesson")
    concept_names: List[str] = Field(
        default_factory=list,
        description="Names of concepts grouped into this lesson"
    )
    estimated_duration_minutes: int = Field(
        default=30,
        description="Estimated duration in minutes"
    )


class RawLessonGroupingResponse(BaseModel):
    """Structured LLM response container for lesson grouping."""
    lessons: List[RawLessonGrouping] = Field(
        default_factory=list,
        description="List of proposed lessons"
    )
