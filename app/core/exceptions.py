from typing import Any, Optional


class AIBrainException(Exception):
    """Base domain exception for AI Brain service."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class ConfigurationError(AIBrainException):
    """Raised when an environment variable or setting is invalid or missing."""
    pass


class LLMServiceError(AIBrainException):
    """Raised when an interaction with the Gemini API fails or is unconfigured."""
    pass


class LLMQuotaExceededError(LLMServiceError):
    """Raised when the Gemini API returns 429 RESOURCE_EXHAUSTED (rate / quota limit).

    Carries ``retry_after_seconds`` parsed from the API response so callers
    and HTTP handlers can surface a proper ``Retry-After`` header.
    """

    def __init__(self, message: str, retry_after_seconds: float = 60.0, details=None):
        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class DatabaseError(AIBrainException):
    """Raised when a database query or session operation fails."""
    pass


class ResourceNotFoundError(AIBrainException):
    """Raised when a requested entity does not exist."""
    pass


class DocumentProcessingError(AIBrainException):
    """Raised when a document cannot be processed or parsed."""
    pass


class UnsupportedFileTypeError(DocumentProcessingError):
    """Raised when a document file extension or MIME type is not supported."""
    pass


class EmptyDocumentError(DocumentProcessingError):
    """Raised when an extracted document contains no readable text."""
    pass


class DocumentNotFoundError(ResourceNotFoundError):
    """Raised when a document file does not exist at the given path."""
    pass


class VectorStoreError(AIBrainException):
    """Raised when an operation on the vector store fails."""
    pass


class RAGError(AIBrainException):
    """Base exception for RAG pipeline errors."""
    pass


class EmptyQueryError(RAGError):
    """Raised when a search query is empty or whitespace only."""
    pass


class InvalidParameterError(RAGError):
    """Raised when query or ingestion parameters are invalid."""
    pass


class LessonPlanningError(AIBrainException):
    """Base exception for lesson planning and concept graph domain errors."""
    pass


class EmptyConceptInputError(LessonPlanningError):
    """Raised when concept extraction or planning is attempted on empty inputs."""
    pass


class InvalidConceptError(LessonPlanningError):
    """Raised when a concept fails semantic or structural validation."""
    pass


class InvalidRelationshipError(LessonPlanningError):
    """Raised when a concept relationship references unknown concept IDs or is malformed."""
    pass


class ConceptCycleError(LessonPlanningError):
    """Raised when a circular dependency / cycle is detected in concept prerequisites."""
    pass


class EmptySyllabusError(LessonPlanningError):
    """Raised when a generated syllabus contains no valid lessons or concepts."""
    pass


class AssessmentError(AIBrainException):
    """Base exception for assessment, evaluation, and misconception detection domain errors."""
    pass


class QuestionGenerationError(AssessmentError):
    """Raised when question generation fails or generates ungrounded/invalid content."""
    pass


class InvalidQuestionError(AssessmentError):
    """Raised when a question fails structural, cognitive, or MCQ constraint validation."""
    pass


class InvalidQuestionTypeError(AssessmentError):
    """Raised when an unknown or unsupported question type is requested."""
    pass


class AnswerEvaluationError(AssessmentError):
    """Raised when an answer evaluation fails or receives invalid input."""
    pass


class EmptyAnswerError(AssessmentError):
    """Raised when an evaluation is attempted on an empty or whitespace-only answer."""
    pass


class MisconceptionDetectionError(AssessmentError):
    """Raised when misconception analysis or classification encounters an error."""
    pass


class AdaptiveEngineError(AIBrainException):
    """Base exception for adaptive engine, mastery calculation, and adaptation decision errors."""
    pass


class InvalidMasteryInputError(AdaptiveEngineError):
    """Raised when mastery input scores, attempt counts, or structures are invalid."""
    pass


class InvalidAdaptationDecisionError(AdaptiveEngineError):
    """Raised when an adaptation decision contains contradictory or invalid action parameters."""
    pass


class MissingConceptError(AdaptiveEngineError):
    """Raised when a requested concept or prerequisite cannot be found in the concept graph."""
    pass


class InvalidDifficultyTransitionError(AdaptiveEngineError):
    """Raised when attempting an impossible or out-of-bounds difficulty transition."""
    pass


class LearnerProfileError(AIBrainException):
    """Base exception for learner profile and preference management errors."""
    pass


class InvalidLearnerProfileError(LearnerProfileError):
    """Raised when learner profile data contains invalid values or fails schema validation."""
    pass


class LearnerNotFoundError(LearnerProfileError):
    """Raised when querying or updating a non-existent learner profile."""
    pass


class InvalidProfileUpdateError(LearnerProfileError):
    """Raised when attempting an unsupported or contradictory profile update."""
    pass


class TeacherSessionError(AIBrainException):
    """Base exception for active teaching session and orchestrator errors."""
    pass


class SessionNotFoundError(TeacherSessionError):
    """Raised when a requested teaching session ID does not exist."""
    pass


class InvalidSessionStateError(TeacherSessionError):
    """Raised when an operation is invalid for the current teaching session state."""
    pass


