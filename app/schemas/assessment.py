from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.adaptive import MasteryLevel
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel


class QuestionType(str, Enum):
    """Supported assessment question formats and cognitive styles."""
    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    CONCEPTUAL = "conceptual"
    APPLICATION = "application"


class MisconceptionSeverity(str, Enum):
    """Categorization of misconception pedagogical impact."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Question(BaseModel):
    """Canonical pedagogical question model tied to concept and learning objective."""
    question_id: str = Field(description="Deterministic SHA-256 unique identifier")
    question_type: QuestionType = Field(description="Question format (mcq, short_answer, conceptual, application)")
    question_text: str = Field(description="The prompt or question presented to the learner")
    concept_id: str = Field(description="Primary concept ID being assessed")
    lesson_id: Optional[str] = Field(default=None, description="Optional parent lesson ID")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Target difficulty level of the question"
    )
    learning_objective: str = Field(description="Specific learning objective tested by this question")
    options: List[str] = Field(
        default_factory=list,
        description="Available multiple choice options (populated for MCQ, empty for open-ended)"
    )
    correct_answer: str = Field(description="The reference correct answer or expected response")
    correct_answer_index: Optional[int] = Field(
        default=None,
        description="Index of correct option in options list for MCQ questions"
    )
    explanation: str = Field(description="Detailed pedagogical explanation of the correct solution")
    misconception_hints: List[str] = Field(
        default_factory=list,
        description="Pedagogical hints identifying potential learner misconceptions"
    )
    evaluation_rubric: Optional[str] = Field(
        default=None,
        description="Scoring criteria and acceptable alternative formulations"
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Source document chunk IDs grounding this question (empty in topic_only)"
    )
    source_material_ids: List[str] = Field(
        default_factory=list,
        description="Source material IDs grounding this question (empty in topic_only)"
    )


class StudentAnswer(BaseModel):
    """Learner's submitted answer with optional reasoning context."""
    question_id: str = Field(description="ID of the question answered")
    answer_text: Optional[str] = Field(default=None, description="Free-form text answer for open-ended questions")
    selected_option: Optional[str] = Field(default=None, description="Selected option string for MCQ questions")
    reasoning: Optional[str] = Field(default=None, description="Optional explanation of learner's thought process")
    submitted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of answer submission"
    )


class EvaluationResult(BaseModel):
    """Fine-grained pedagogical evaluation of a learner's answer."""
    evaluation_id: str = Field(description="Deterministic SHA-256 identifier for this evaluation")
    question_id: str = Field(description="ID of the evaluated question")
    concept_id: str = Field(description="Target concept ID")
    correctness: bool = Field(description="High-level correctness flag (True if score >= 0.75)")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized performance score (0.0 to 1.0)"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Evaluator confidence in the assessment (0.0 to 1.0)"
    )
    expected_answer: str = Field(description="The reference benchmark answer")
    student_answer: str = Field(description="The actual answer evaluated")
    concepts_tested: List[str] = Field(
        default_factory=list,
        description="Concepts or facets evaluated by the question"
    )
    concepts_demonstrated: List[str] = Field(
        default_factory=list,
        description="Concepts or principles accurately demonstrated by the student"
    )
    concepts_missing: List[str] = Field(
        default_factory=list,
        description="Required concepts or principles omitted or misrepresented"
    )
    reasoning_assessment: Optional[str] = Field(
        default=None,
        description="Assessment of the student's logical deduction and problem-solving steps"
    )
    evidence: str = Field(description="Specific excerpts or observations justifying the score")
    feedback: str = Field(description="Constructive, non-overwhelming feedback for the learner")


class Misconception(BaseModel):
    """A detected conceptual flaw, flawed mental model, or prerequisite misunderstanding."""
    misconception_id: str = Field(description="Deterministic SHA-256 identifier")
    concept_id: str = Field(description="Concept under which the misconception occurred")
    description: str = Field(description="Clear explanation of the flawed understanding")
    evidence: str = Field(description="Direct evidence from student's answer and reasoning")
    severity: MisconceptionSeverity = Field(
        default=MisconceptionSeverity.MEDIUM,
        description="Pedagogical severity (low, medium, high)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Detector confidence that this is a genuine misconception (0.0 to 1.0)"
    )
    affected_concept_ids: List[str] = Field(
        default_factory=list,
        description="IDs of other concepts potentially impacted by this misunderstanding"
    )
    source_question_id: str = Field(description="Question ID where the misconception was observed")
    source_evaluation_id: Optional[str] = Field(
        default=None,
        description="Optional EvaluationResult ID containing the assessment evidence"
    )
    recommended_focus: Optional[str] = Field(
        default=None,
        description="Suggested conceptual focus or clarification topic"
    )


class MisconceptionAnalysis(BaseModel):
    """Aggregate result of misconception diagnosis for an answer evaluation."""
    detected: bool = Field(description="True if one or more genuine misconceptions were identified")
    misconceptions: List[Misconception] = Field(
        default_factory=list,
        description="List of detected misconceptions"
    )
    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence across detected items"
    )
    summary: str = Field(description="Pedagogical summary of diagnosed understanding")


# ====================================================================
# Intermediate Pydantic Schemas for Structured LLM Interaction
# ====================================================================

class RawGeneratedQuestion(BaseModel):
    """Semantic question payload returned by LLM prior to ID and schema validation."""
    question_type: QuestionType = Field(description="Question format")
    question_text: str = Field(description="Question text")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Difficulty level"
    )
    learning_objective: str = Field(description="Target learning objective")
    options: List[str] = Field(
        default_factory=list,
        description="Options for MCQ, empty for other types"
    )
    correct_answer: str = Field(description="Expected correct answer")
    correct_answer_index: Optional[int] = Field(
        default=None,
        description="Index of correct option in options list for MCQ questions"
    )
    explanation: str = Field(description="Explanation of correct answer")
    misconception_hints: List[str] = Field(
        default_factory=list,
        description="Pedagogical hints identifying potential learner misconceptions"
    )
    evaluation_rubric: Optional[str] = Field(default=None, description="Evaluation rubric")


class RawQuestionBatchResponse(BaseModel):
    """Structured LLM response container for question generation."""
    questions: List[RawGeneratedQuestion] = Field(
        default_factory=list,
        description="List of generated questions"
    )


class RawAnswerEvaluationResponse(BaseModel):
    """Structured LLM response container for open-ended answer evaluation."""
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Evaluation score between 0.0 and 1.0"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence in evaluation"
    )
    concepts_tested: List[str] = Field(
        default_factory=list,
        description="List of concepts tested"
    )
    concepts_demonstrated: List[str] = Field(
        default_factory=list,
        description="Concepts correctly demonstrated"
    )
    concepts_missing: List[str] = Field(
        default_factory=list,
        description="Concepts missing or flawed"
    )
    reasoning_assessment: Optional[str] = Field(
        default=None,
        description="Critique of student reasoning"
    )
    evidence: str = Field(description="Justification for the score")
    feedback: str = Field(description="Feedback message for student")


class RawMisconceptionItem(BaseModel):
    """Semantic payload for an individual misconception identified by LLM."""
    description: str = Field(description="Description of the conceptual flaw")
    evidence: str = Field(description="Evidence from student answer")
    severity: MisconceptionSeverity = Field(
        default=MisconceptionSeverity.MEDIUM,
        description="Severity level"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence that this is a genuine conceptual misconception and not a slip"
    )
    is_prerequisite_flaw: bool = Field(
        default=False,
        description="True if the misconception stems from a fundamental prerequisite"
    )
    recommended_focus: Optional[str] = Field(
        default=None,
        description="Pedagogical focus for remediation"
    )


class RawMisconceptionDetectionResponse(BaseModel):
    """Structured LLM response container for misconception detection."""
    is_genuine_misconception: bool = Field(
        description="True if errors represent genuine conceptual misunderstandings rather than slips or typos"
    )
    misconceptions: List[RawMisconceptionItem] = Field(
        default_factory=list,
        description="List of detected misconceptions"
    )
    summary: str = Field(description="Brief diagnosis summary")


# ====================================================================
# Final Assessment & Learning Report Schemas
# ====================================================================

class ConceptReportItem(BaseModel):
    """Per-concept mastery breakdown within an assessment report."""
    concept_id: str = Field(description="Unique concept identifier")
    concept_name: str = Field(description="Human-readable concept name")
    score: float = Field(ge=0.0, le=1.0, description="Normalized score on this concept (0.0 to 1.0)")
    mastery_level: MasteryLevel = Field(description="Achieved mastery level")
    status: str = Field(description="Status label: 'mastered', 'in_progress', or 'needs_review'")
    attempts: int = Field(default=1, description="Number of questions evaluated for this concept")


class AssessmentReport(BaseModel):
    """Comprehensive diagnostic learning report generated upon assessment completion."""
    report_id: str = Field(description="Unique report identifier")
    learner_id: str = Field(description="Learner identifier")
    session_id: Optional[str] = Field(default=None, description="Associated session log ID")
    lesson_id: Optional[str] = Field(default=None, description="Associated lesson ID")
    overall_score: float = Field(ge=0.0, le=1.0, description="Overall weighted score across all evaluated concepts")
    overall_mastery_level: MasteryLevel = Field(description="Overall mastery classification")
    letter_grade: str = Field(description="Academic grade: A+, A, B, C, D, or F")
    total_questions: int = Field(description="Total assessment questions evaluated")
    correct_answers: int = Field(description="Number of questions answered correctly (score >= 0.75)")
    concept_breakdowns: List[ConceptReportItem] = Field(
        default_factory=list,
        description="Detailed performance breakdown per concept"
    )
    misconceptions_detected: List[Misconception] = Field(
        default_factory=list,
        description="All diagnosed misconceptions with pedagogical evidence and severity"
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Key conceptual strengths demonstrated during the assessment"
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Concepts or areas requiring targeted review and reinforcement"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable next-step study items and remediation advice"
    )
    summary: str = Field(description="Executive pedagogical summary of learner performance")
    language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Language in which the report summary and recommendations are phrased"
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 generation timestamp"
    )


class FinalAssessmentRequest(BaseModel):
    """Request payload for generating a multi-concept final assessment package."""
    learner_id: str = Field(description="Learner ID")
    lesson_id: Optional[str] = Field(default=None, description="Lesson ID to assess")
    session_id: Optional[str] = Field(default=None, description="Active session ID if continuing from a live session")
    concept_ids: List[str] = Field(default_factory=list, description="Target concept IDs to include in the exam")
    num_questions: int = Field(default=5, ge=1, le=20, description="Total number of assessment questions to generate")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE, description="Baseline question difficulty")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Target instructional language")


class FinalAssessmentPackage(BaseModel):
    """Collection of assessment questions delivered to the student."""
    assessment_id: str = Field(description="Unique exam session identifier")
    learner_id: str = Field(description="Learner ID")
    lesson_id: Optional[str] = Field(default=None, description="Lesson ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    questions: List[Question] = Field(default_factory=list, description="Ordered assessment questions")
    total_questions: int = Field(description="Total question count")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 generation timestamp"
    )


class FinalAssessmentSubmission(BaseModel):
    """Student submission of all answered questions for a final assessment."""
    assessment_id: str = Field(description="Assessment package ID being submitted")
    learner_id: str = Field(description="Learner ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    lesson_id: Optional[str] = Field(default=None, description="Lesson ID")
    answers: List[StudentAnswer] = Field(default_factory=list, description="Answers submitted by the learner")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Instructional language")


class RawAssessmentReportPayload(BaseModel):
    """Structured LLM output schema for generating diagnostic assessment summaries."""
    summary: str = Field(description="Executive pedagogical summary of performance")
    strengths: List[str] = Field(description="List of observed conceptual strengths")
    weaknesses: List[str] = Field(description="List of areas needing improvement")
    recommendations: List[str] = Field(description="Actionable study recommendations")
