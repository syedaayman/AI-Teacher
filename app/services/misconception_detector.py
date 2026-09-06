import hashlib
import logging
import re
from typing import List, Optional

from app.core.exceptions import (
    AnswerEvaluationError,
    InvalidQuestionError,
    MisconceptionDetectionError,
)
from app.core.gemini import gemini_client
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    RawMisconceptionDetectionResponse,
    StudentAnswer,
)
from app.schemas.lesson import Concept

logger = logging.getLogger(__name__)


class MisconceptionDetector:
    """Domain service for diagnosing genuine conceptual and prerequisite misconceptions from answer evaluations."""

    def __init__(self, client=None):
        self._gemini_client = client or gemini_client

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_misconception_id(
        concept_id: str,
        question_id: str,
        description: str,
    ) -> str:
        """Generate a deterministic SHA-256 identifier for a diagnosed misconception."""
        if not concept_id or not question_id or not description:
            raise MisconceptionDetectionError("Cannot generate misconception ID with missing parameters.")
        norm_desc = re.sub(r"\s+", " ", description.strip().lower())
        seed = f"{concept_id}:{question_id}:{norm_desc}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"msc_{digest}"

    # ----------------------------------------------------------------
    # Misconception Analysis
    # ----------------------------------------------------------------

    async def detect_misconceptions(
        self,
        question: Question,
        student_answer: StudentAnswer,
        evaluation_result: EvaluationResult,
        concept: Optional[Concept] = None,
        prerequisite_concepts: Optional[List[Concept]] = None,
        concept_graph: Optional[Any] = None,
        **kwargs: Any,
    ) -> MisconceptionAnalysis:
        """Analyze an answer evaluation to detect genuine conceptual or prerequisite flaws."""
        if not question:
            raise InvalidQuestionError("Question cannot be None.")
        if not student_answer:
            raise AnswerEvaluationError("Student answer cannot be None.")
        if not evaluation_result:
            raise MisconceptionDetectionError("EvaluationResult cannot be None.")

        # If answer is fully correct and no concepts are missing, return early
        if evaluation_result.score >= 0.99 and not evaluation_result.concepts_missing:
            return MisconceptionAnalysis(
                detected=False,
                misconceptions=[],
                overall_confidence=1.0,
                summary="Answer is fully correct. No conceptual misconceptions detected.",
            )

        # Context on prerequisites if available
        prereq_info = ""
        if concept and concept.prerequisite_concept_ids:
            prereq_info = f"Prerequisite Concept IDs: {', '.join(concept.prerequisite_concept_ids)}"
        if prerequisite_concepts:
            prereq_names = [f"{p.name} ({p.concept_id})" for p in prerequisite_concepts]
            prereq_info += f"\nKnown Prerequisite Concepts: {', '.join(prereq_names)}"

        system_instruction = (
            "You are an expert pedagogical diagnostician for an AI Teacher system.\n"
            "Analyze the student's incorrect or partial answer and the evaluation result to determine if there is a genuine conceptual misconception.\n\n"
            "Classification Rules:\n"
            "1. Do NOT classify simple slips, typographical mistakes, or minor arithmetic slips as misconceptions.\n"
            "2. Distinguish between:\n"
            "   - Simple slip/typo: Student understands the concept but made a trivial superficial mistake (is_genuine_misconception = False).\n"
            "   - Incomplete understanding: Student forgot a detail or gave an incomplete answer but has no flawed mental model (is_genuine_misconception = False).\n"
            "   - Conceptual Misconception: Student holds an actively incorrect mental model or fundamentally misinterprets the principle (is_genuine_misconception = True).\n"
            "   - Prerequisite Misconception: The student's error stems from a failure to understand an underlying prerequisite concept (is_prerequisite_flaw = True).\n"
            "3. Provide clear evidence from the student's answer.\n"
            "4. Multilingual & Idiomatic Recognition: The student's answer and reasoning may be expressed in English, "
            "Hindi (Devanagari), or Hinglish (conversational Latin script). Accurately diagnose whether an incorrect "
            "mental model is present regardless of whether the phrasing uses Hindi or Hinglish technical idioms."
        )

        prompt = (
            f"Target Concept ID: {question.concept_id}\n"
            f"Question: {question.question_text}\n"
            f"Expected Answer: {question.correct_answer}\n"
            f"Student Answer: {evaluation_result.student_answer}\n"
            f"Reasoning Provided: {student_answer.reasoning or 'None'}\n"
            f"Evaluation Score: {evaluation_result.score}\n"
            f"Evaluation Evidence: {evaluation_result.evidence}\n"
            f"Missing Concepts: {', '.join(evaluation_result.concepts_missing)}\n"
            f"{prereq_info}\n\n"
            "Diagnose whether any genuine conceptual or prerequisite misconceptions exist."
        )

        try:
            raw_response = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawMisconceptionDetectionResponse,
                system_instruction=system_instruction,
            )
        except Exception as ex:
            logger.warning("LLM misconception detection failed, using deterministic fallback: %s", ex)
            if evaluation_result.score < 0.6:
                m_id = self.generate_misconception_id(
                    concept_id=question.concept_id,
                    question_id=question.question_id,
                    description=f"Conceptual gap in {question.learning_objective}",
                )
                fallback_m = Misconception(
                    misconception_id=m_id,
                    concept_id=question.concept_id,
                    description=f"Misunderstanding of key mechanism in {question.learning_objective}.",
                    evidence=evaluation_result.evidence or "Student explanation omitted core conceptual mechanism.",
                    severity=MisconceptionSeverity.MEDIUM,
                    confidence=0.8,
                    affected_concept_ids=[question.concept_id],
                    source_question_id=question.question_id,
                    source_evaluation_id=evaluation_result.evaluation_id,
                    recommended_focus=question.explanation or question.learning_objective,
                )
                return MisconceptionAnalysis(
                    detected=True,
                    misconceptions=[fallback_m],
                    overall_confidence=0.8,
                    summary=f"Conceptual flaw detected in {question.learning_objective}.",
                )
            else:
                return MisconceptionAnalysis(
                    detected=False,
                    misconceptions=[],
                    overall_confidence=0.9,
                    summary="No conceptual misconception detected.",
                )

        if not raw_response.is_genuine_misconception or not raw_response.misconceptions:
            return MisconceptionAnalysis(
                detected=False,
                misconceptions=[],
                overall_confidence=1.0,
                summary=raw_response.summary or "No genuine conceptual misconceptions detected (mistake is a minor slip or incomplete response).",
            )

        diagnosed_misconceptions: List[Misconception] = []
        for raw_item in raw_response.misconceptions:
            m_id = self.generate_misconception_id(
                concept_id=question.concept_id,
                question_id=question.question_id,
                description=raw_item.description,
            )

            # Determine affected concepts
            affected_ids = [question.concept_id]
            if raw_item.is_prerequisite_flaw and concept and concept.prerequisite_concept_ids:
                for pid in concept.prerequisite_concept_ids:
                    if pid not in affected_ids:
                        affected_ids.append(pid)

            clamped_conf = max(0.0, min(1.0, float(raw_item.confidence)))

            diagnosed_misconceptions.append(
                Misconception(
                    misconception_id=m_id,
                    concept_id=question.concept_id,
                    description=raw_item.description.strip(),
                    evidence=raw_item.evidence.strip(),
                    severity=raw_item.severity or MisconceptionSeverity.MEDIUM,
                    confidence=clamped_conf,
                    affected_concept_ids=affected_ids,
                    source_question_id=question.question_id,
                    source_evaluation_id=evaluation_result.evaluation_id,
                    recommended_focus=raw_item.recommended_focus,
                )
            )

        avg_conf = (
            sum(m.confidence for m in diagnosed_misconceptions) / len(diagnosed_misconceptions)
            if diagnosed_misconceptions else 1.0
        )

        return MisconceptionAnalysis(
            detected=bool(diagnosed_misconceptions),
            misconceptions=diagnosed_misconceptions,
            overall_confidence=avg_conf,
            summary=raw_response.summary or f"Diagnosed {len(diagnosed_misconceptions)} conceptual misconception(s).",
        )


# Singleton service instance
misconception_detector = MisconceptionDetector()
