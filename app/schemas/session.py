from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.adaptive import AdaptationDecision
from app.schemas.assessment import (
    EvaluationResult,
    MisconceptionAnalysis,
    Question,
    StudentAnswer,
)
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel


class TeachingStep(str, Enum):
    """Pedagogical stages within the AI Teacher instructional loop."""
    UNDERSTAND = "understand"
    PLAN = "plan"
    EXPLAIN = "explain"
    DEMONSTRATE = "demonstrate"
    QUESTION = "question"
    EVALUATE = "evaluate"
    ADAPT = "adapt"
    COMPLETE = "complete"


class SessionStatus(str, Enum):
    """Operational lifecycle status of an active teaching session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class InstructionalDelivery(BaseModel):
    """Pedagogical explanation or demonstration payload produced by the teacher."""
    step: TeachingStep = Field(description="Teaching step (explain or demonstrate)")
    concept_id: str = Field(description="ID of the concept being taught")
    concept_name: str = Field(description="Display title of the concept")
    title: str = Field(description="Instructional section title")
    content: str = Field(description="Core explanation or demonstration narrative")
    visual_description: Optional[str] = Field(
        default=None,
        description="Structured visual/board description for Member 2 UI rendering",
    )
    diagram_required: bool = Field(
        default=False,
        description="Flag indicating Member 2 should render a diagram/visual graphic",
    )
    code_snippet: Optional[str] = Field(
        default=None,
        description="Optional runnable code or syntax example",
    )
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="Key conceptual bullet points for learner retention",
    )
    analogy: Optional[str] = Field(
        default=None,
        description="Intuitive real-world or physical analogy",
    )
    real_world_application: Optional[str] = Field(
        default=None,
        description="Practical engineering or real-world use case",
    )
    counter_example: Optional[str] = Field(
        default=None,
        description="Clarifying counter-example or anti-pattern to prevent misunderstandings",
    )
    language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Language in which content was rendered",
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Difficulty level of the instructional delivery",
    )
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of source document citations and metadata when teaching from uploaded materials",
    )


class LessonSessionState(BaseModel):
    """Comprehensive state tracking an active human-like teaching session."""
    session_id: str = Field(description="Unique deterministic session identifier")
    learner_id: str = Field(description="Identifier of the learner")
    topic: Optional[str] = Field(default=None, description="Curriculum topic being taught")
    material_id: Optional[str] = Field(default=None, description="Optional uploaded learning material ID")
    lesson_id: Optional[str] = Field(default=None, description="Optional lesson plan ID")
    concepts: List[str] = Field(
        default_factory=list,
        description="Ordered sequence of concept IDs in this session's learning path",
    )
    concept_names: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from concept_id to human-readable concept name",
    )
    current_concept_index: int = Field(
        default=0,
        ge=0,
        description="0-based index into the concepts sequence",
    )
    current_step: TeachingStep = Field(
        default=TeachingStep.EXPLAIN,
        description="Current step in the teaching loop",
    )
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        description="Lifecycle status of this session",
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Current adaptive difficulty level",
    )
    language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Active teaching language",
    )
    time_budget_minutes: int = Field(
        default=20,
        ge=1,
        description="Total allocated session duration in minutes",
    )
    remaining_time_minutes: int = Field(
        default=20,
        ge=0,
        description="Estimated remaining session time in minutes",
    )
    desired_depth: str = Field(
        default="standard",
        description="Instructional depth mode ('quick_overview', 'standard', 'deep_dive')",
    )
    step_count: int = Field(
        default=0,
        ge=0,
        description="Total instructional steps executed in this session",
    )
    remediation_attempts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of remediation attempts per concept ID (capped to prevent infinite loops)",
    )
    completed_concepts: List[str] = Field(
        default_factory=list,
        description="List of concept IDs mastered or completed in this session",
    )
    current_delivery: Optional[InstructionalDelivery] = Field(
        default=None,
        description="Most recent explanation or demonstration delivery",
    )
    last_question: Optional[Question] = Field(
        default=None,
        description="Most recently presented assessment question",
    )
    last_student_answer: Optional[StudentAnswer] = Field(
        default=None,
        description="Most recent answer submitted by the learner",
    )
    last_evaluation: Optional[EvaluationResult] = Field(
        default=None,
        description="Evaluation result of the last answer",
    )
    last_misconception_analysis: Optional[MisconceptionAnalysis] = Field(
        default=None,
        description="Misconception diagnosis from the last answer",
    )
    last_adaptation: Optional[AdaptationDecision] = Field(
        default=None,
        description="Most recent pedagogical adaptation decision",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Linear log of step interactions during the session",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session start timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session last modified timestamp",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="Session completion timestamp",
    )

    @property
    def current_concept_id(self) -> Optional[str]:
        """Return the active concept ID based on current_concept_index."""
        if 0 <= self.current_concept_index < len(self.concepts):
            return self.concepts[self.current_concept_index]
        return None

    @property
    def current_concept_name(self) -> Optional[str]:
        """Return human-readable name of the active concept."""
        cid = self.current_concept_id
        if cid:
            return self.concept_names.get(cid, cid)
        return None

    @property
    def is_completed(self) -> bool:
        """Check if the session has concluded."""
        return self.status == SessionStatus.COMPLETED or self.current_step == TeachingStep.COMPLETE


# --------------------------------------------------------------------
# API Request & Response Schemas
# --------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    """Payload to initiate an adaptive teaching session."""
    learner_id: str = Field(description="Unique learner identifier")
    topic: Optional[str] = Field(default=None, description="Topic to teach if no material uploaded")
    material_id: Optional[str] = Field(default=None, description="Uploaded material ID for grounded teaching")
    lesson_id: Optional[str] = Field(default=None, description="Specific lesson ID from syllabus")
    concept_ids: Optional[List[str]] = Field(default=None, description="Specific sequence of concepts")
    available_time_minutes: int = Field(default=20, ge=1, le=180, description="Available session duration")
    desired_depth: str = Field(default="standard", description="'quick_overview', 'standard', or 'deep_dive'")
    preferred_language: Optional[SupportedLanguage] = Field(default=None, description="Language override")
    preferred_difficulty: Optional[DifficultyLevel] = Field(default=None, description="Difficulty override")


class SubmitAnswerRequest(BaseModel):
    """Payload when learner responds to an assessment question."""
    session_id: str = Field(description="Active session ID")
    learner_id: str = Field(description="Learner ID submitting answer")
    question_id: str = Field(description="Question ID being answered")
    answer_text: Optional[str] = Field(default=None, description="Open-ended textual answer")
    selected_option: Optional[str] = Field(default=None, description="Selected option for MCQ")
    reasoning: Optional[str] = Field(default=None, description="Learner's thought process explanation")


class AdvanceStepRequest(BaseModel):
    """Payload to advance to the next step (e.g. from Explain to Demonstrate, or Demonstrate to Question)."""
    session_id: str = Field(description="Active session ID")
    learner_id: str = Field(description="Learner ID")


class SwitchLanguageRequest(BaseModel):
    """Payload to change instructional language mid-session."""
    session_id: str = Field(description="Active session ID")
    language: SupportedLanguage = Field(description="New target instructional language")


class SessionStepResponse(BaseModel):
    """Unified response containing the current instructional state and teacher output."""
    session_id: str
    learner_id: str
    current_step: TeachingStep
    status: SessionStatus
    current_concept_id: Optional[str] = None
    current_concept_name: Optional[str] = None
    concept_index: int = 0
    total_concepts: int = 0
    difficulty: DifficultyLevel
    language: SupportedLanguage
    remaining_time_minutes: int
    step_count: int = 0
    delivery: Optional[InstructionalDelivery] = None
    question: Optional[Question] = None
    evaluation: Optional[EvaluationResult] = None
    misconception_analysis: Optional[MisconceptionAnalysis] = None
    adaptation: Optional[AdaptationDecision] = None
    message: str = ""
