from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.adaptive import (
    AdaptationDecision,
    ConceptMastery,
    MasteryLevel,
)
from app.schemas.assessment import (
    EvaluationResult,
    MisconceptionAnalysis,
    Question,
    QuestionType,
    StudentAnswer,
)
from app.schemas.learner import LearnerProfile, SupportedLanguage
from app.schemas.lesson import Concept, ConceptGraph, DifficultyLevel, Syllabus
from app.schemas.material import DocumentChunk, ExtractedDocument
from app.schemas.rag import GroundedContext, IngestionResult, RetrievedChunk, VectorStoreStats


class MaterialProcessingResponse(BaseModel):
    """Response combining Phase 2 extraction and optional Phase 3 vector ingestion."""
    extracted_document: ExtractedDocument = Field(description="Normalized document chunks and metadata")
    ingestion_result: Optional[IngestionResult] = Field(
        default=None,
        description="Vector store chunk ingestion statistics if indexing was enabled"
    )


class RAGSearchRequest(BaseModel):
    """Semantic search query request."""
    query: str = Field(min_length=1, description="Search query string")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of relevant chunks to retrieve")
    material_id: Optional[str] = Field(default=None, description="Optional material filter")


class RAGSearchResponse(BaseModel):
    """Semantic search results response."""
    query: str
    results: List[RetrievedChunk]


class RAGContextRequest(BaseModel):
    """Grounded prompt context construction request."""
    query: str = Field(min_length=1, description="Query string to ground")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to include in context")
    material_id: Optional[str] = Field(default=None, description="Optional material filter")


class ConceptExtractionRequest(BaseModel):
    """Pedagogical concept extraction request."""
    topic: Optional[str] = Field(default=None, description="Topic name for topic-only extraction")
    document: Optional[ExtractedDocument] = Field(default=None, description="Material document for grounded extraction")
    material_id: Optional[str] = Field(default=None, description="Material ID if already ingested")


class ConceptGraphRequest(BaseModel):
    """Concept graph and topological sort construction request."""
    concepts: List[Concept] = Field(min_length=1, description="List of concepts to graph")


class ConceptGraphResponse(BaseModel):
    """Constructed concept graph and valid topological ordering."""
    graph: ConceptGraph
    topological_order: List[Concept]


class LessonPlanRequest(BaseModel):
    """Lesson planning and syllabus generation request."""
    topic: Optional[str] = Field(default=None, description="Topic name for topic-only planning")
    document: Optional[ExtractedDocument] = Field(default=None, description="Document for material-grounded planning")
    title: Optional[str] = Field(default=None, description="Optional syllabus title")


class QuestionGenerationRequest(BaseModel):
    """Assessment question generation request."""
    concept: Concept = Field(description="Target concept for question generation")
    question_type: QuestionType = Field(default=QuestionType.MCQ, description="Type of question to generate")
    count: int = Field(default=1, ge=1, le=5, description="Number of questions to generate")
    lesson_id: Optional[str] = Field(default=None, description="Optional associated lesson ID")


class AnswerEvaluationRequest(BaseModel):
    """Assessment answer evaluation request."""
    question: Question = Field(description="Question being answered")
    student_answer: StudentAnswer = Field(description="Student's submission")


class MisconceptionDetectionRequest(BaseModel):
    """Assessment misconception diagnosis request."""
    question: Question = Field(description="Question under assessment")
    student_answer: StudentAnswer = Field(description="Student's submission")
    evaluation_result: EvaluationResult = Field(description="Evaluation output from AnswerEvaluator")
    concept: Concept = Field(description="Target concept")
    concept_graph: Optional[ConceptGraph] = Field(default=None, description="Optional prerequisite graph")


class MasteryUpdateRequest(BaseModel):
    """Concept mastery update request."""
    concept_id: str = Field(min_length=1, description="Concept identifier")
    evaluation_result: EvaluationResult = Field(description="Assessment evaluation result")
    previous_mastery: Optional[ConceptMastery] = Field(default=None, description="Existing mastery record if any")


class AdaptiveDecisionRequest(BaseModel):
    """Adaptive pedagogical decision request."""
    current_concept_id: str = Field(min_length=1, description="Active concept ID")
    current_difficulty: DifficultyLevel = Field(description="Current instructional difficulty")
    evaluation_result: EvaluationResult = Field(description="Evaluation output")
    concept_mastery: ConceptMastery = Field(description="Current concept mastery record")
    misconception_analysis: Optional[MisconceptionAnalysis] = Field(default=None, description="Diagnosed misconceptions")
    concept_graph: Optional[ConceptGraph] = Field(default=None, description="Curriculum concept graph")
    learner_id: Optional[str] = Field(default=None, description="Optional learner ID")
    session_id: Optional[str] = Field(default=None, description="Optional session ID")


class CreateProfileRequest(BaseModel):
    """Learner profile creation request."""
    learner_id: str = Field(min_length=1, description="Unique learner identifier")
    name: Optional[str] = Field(default=None, description="Learner name/handle")
    preferred_language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Preferred language")
    learning_goal: Optional[str] = Field(default=None, description="Curriculum goal")
    preferred_difficulty: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE, description="Starting difficulty")
    total_lessons: int = Field(default=0, ge=0, description="Total lessons in curriculum")


class UpdatePreferencesRequest(BaseModel):
    """Learner preferences update request."""
    learner_id: str = Field(min_length=1, description="Learner ID to update")
    preferred_language: Optional[SupportedLanguage] = None
    preferred_difficulty: Optional[DifficultyLevel] = None
    learning_goal: Optional[str] = None


class UpdateMasteryRequest(BaseModel):
    """Learner concept mastery update request."""
    learner_id: str = Field(min_length=1, description="Target learner ID")
    concept_mastery: ConceptMastery = Field(description="Concept mastery record")


class RecordLessonRequest(BaseModel):
    """Lesson completion recording request."""
    learner_id: str = Field(min_length=1, description="Target learner ID")
    lesson_id: str = Field(min_length=1, description="Completed lesson ID")


class RecordAssessmentRequest(BaseModel):
    """Assessment score recording request."""
    learner_id: str = Field(min_length=1, description="Target learner ID")
    score: float = Field(ge=0.0, le=1.0, description="Assessment score")


class SevenDayPlanRequest(BaseModel):
    """Request to generate a personalized 7-day learning schedule."""
    topic: Optional[str] = Field(default="Course", description="Topic title")
    document: Optional[ExtractedDocument] = Field(default=None, description="Material document if grounded")
    daily_minutes: int = Field(default=30, ge=10, le=180, description="Available minutes per day")
    learner_id: Optional[str] = Field(default=None, description="Optional learner ID for profile grounding")


class VideoPlanRequest(BaseModel):
    """Request for lesson teaching video storyboard and scene sequencing."""
    topic: str = Field(description="Lesson topic")
    concept_name: str = Field(description="Active concept name")
    concept_id: Optional[str] = Field(default=None, description="Concept identifier")
    delivery_content: Optional[str] = Field(default=None, description="Spoken teacher dialogue")
    language: str = Field(default="english", description="Delivery language")


class VideoGenerateRequest(BaseModel):
    """Request to compose and render actual playable lesson video artifact."""
    topic: str = Field(description="Lesson topic")
    concept_name: str = Field(description="Active concept name")
    scenes: Optional[List[dict]] = Field(default=None, description="Pre-planned scenes")
    provider: Optional[str] = Field(default="local_canvas_composer", description="Preferred video provider")

