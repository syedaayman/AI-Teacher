import hashlib
import logging
import re
from typing import Optional

from app.core.exceptions import (
    AnswerEvaluationError,
    EmptyAnswerError,
    InvalidQuestionError,
)
from app.core.gemini import gemini_client
from app.schemas.assessment import (
    EvaluationResult,
    Question,
    QuestionType,
    RawAnswerEvaluationResponse,
    StudentAnswer,
)

logger = logging.getLogger(__name__)


class AnswerEvaluator:
    """Domain service for evaluating learner answers with fine-grained evidence and feedback."""

    def __init__(self, client=None):
        self._gemini_client = client or gemini_client

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_evaluation_id(
        question_id: str,
        concept_id: str,
        student_response: str,
    ) -> str:
        """Generate a deterministic SHA-256 evaluation ID."""
        if not question_id or not concept_id:
            raise AnswerEvaluationError("Cannot generate evaluation ID without question_id and concept_id.")
        norm_resp = re.sub(r"\s+", " ", (student_response or "").strip().lower())
        seed = f"{question_id}:{concept_id}:{norm_resp}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"eval_{digest}"

    # ----------------------------------------------------------------
    # Main Evaluation Interface
    # ----------------------------------------------------------------

    async def evaluate_answer(
        self,
        question: Question,
        student_answer: StudentAnswer,
    ) -> EvaluationResult:
        """Evaluate a learner's answer against a question rubric and return a structured EvaluationResult."""
        if not question:
            raise InvalidQuestionError("Question cannot be None.")
        if not student_answer:
            raise AnswerEvaluationError("Student answer cannot be None.")

        if question.question_id != student_answer.question_id:
            raise AnswerEvaluationError(
                f"Question ID mismatch: Question has '{question.question_id}', answer has '{student_answer.question_id}'."
            )

        # Extract submitted answer content
        raw_submission = student_answer.selected_option or student_answer.answer_text
        if not raw_submission or not raw_submission.strip():
            raise EmptyAnswerError("Student answer is empty or whitespace.")

        clean_submission = raw_submission.strip()

        # Route evaluation strategy
        if question.question_type == QuestionType.MCQ:
            return self._evaluate_mcq(question, student_answer, clean_submission)
        else:
            return await self._evaluate_open_ended(question, student_answer, clean_submission)

    # ----------------------------------------------------------------
    # MCQ Evaluation (Deterministic)
    # ----------------------------------------------------------------

    def _evaluate_mcq(
        self,
        question: Question,
        student_answer: StudentAnswer,
        submission: str,
    ) -> EvaluationResult:
        """Deterministically evaluate multiple choice question submission."""
        correct_norm = question.correct_answer.strip().lower()
        sub_norm = submission.strip().lower()

        # Direct match or letter-option match
        is_correct = (sub_norm == correct_norm)

        # Check prefix matching (e.g. user submitted "A" or "A) Option text")
        if not is_correct and question.options:
            for idx, opt in enumerate(question.options):
                opt_norm = opt.strip().lower()
                letter = chr(65 + idx).lower()  # a, b, c, d
                if (sub_norm == letter and opt_norm == correct_norm) or \
                   (correct_norm == letter and sub_norm == opt_norm):
                    is_correct = True
                    break

        score = 1.0 if is_correct else 0.0
        eval_id = self.generate_evaluation_id(
            question_id=question.question_id,
            concept_id=question.concept_id,
            student_response=submission,
        )

        if is_correct:
            evidence = f"Selected option '{submission}' matches the correct answer."
            feedback = f"Correct! {question.explanation}"
            concepts_demonstrated = [question.learning_objective]
            concepts_missing = []
        else:
            evidence = f"Selected option '{submission}' is incorrect. Expected '{question.correct_answer}'."
            feedback = f"Incorrect. The correct answer is: {question.correct_answer}. {question.explanation}"
            concepts_demonstrated = []
            concepts_missing = [question.learning_objective]

        return EvaluationResult(
            evaluation_id=eval_id,
            question_id=question.question_id,
            concept_id=question.concept_id,
            correctness=is_correct,
            score=score,
            confidence=1.0,
            expected_answer=question.correct_answer,
            student_answer=submission,
            concepts_tested=[question.learning_objective],
            concepts_demonstrated=concepts_demonstrated,
            concepts_missing=concepts_missing,
            reasoning_assessment="Deterministic option selection evaluation.",
            evidence=evidence,
            feedback=feedback,
        )

    # ----------------------------------------------------------------
    # Open-Ended Answer Evaluation (Semantic LLM)
    # ----------------------------------------------------------------

    async def _evaluate_open_ended(
        self,
        question: Question,
        student_answer: StudentAnswer,
        submission: str,
    ) -> EvaluationResult:
        """Semantically evaluate open-ended questions using structured LLM analysis."""
        system_instruction = (
            "You are an expert pedagogical assessor for an AI Teacher system.\n"
            "Evaluate the student's answer accurately against the benchmark answer and learning objective.\n\n"
            "Guidelines:\n"
            "1. Score the answer from 0.0 to 1.0 based on conceptual accuracy and depth:\n"
            "   - 1.0: Fully correct, comprehensive explanation\n"
            "   - 0.75: Mostly correct, minor omission or phrasing flaw\n"
            "   - 0.5: Partial understanding, key concept mentioned but incomplete or partially flawed\n"
            "   - 0.25: Minimal understanding or tangential answer\n"
            "   - 0.0: Completely incorrect or irrelevant\n"
            "2. Identify specific concepts demonstrated and concepts missing.\n"
            "3. Provide concrete evidence pointing to the student's text.\n"
            "4. Provide constructive, encouraging feedback without overwhelming the student."
        )

        reasoning_context = f"\nStudent Reasoning: {student_answer.reasoning.strip()}" if student_answer.reasoning else ""
        prompt = (
            f"Question Text: {question.question_text}\n"
            f"Target Learning Objective: {question.learning_objective}\n"
            f"Expected Reference Answer: {question.correct_answer}\n"
            f"Explanation: {question.explanation}\n"
            f"Rubric: {question.evaluation_rubric or 'Evaluate for core conceptual correctness and reasoning.'}\n\n"
            f"Student Answer: {submission}{reasoning_context}"
        )

        raw_eval = await self._gemini_client.generate_structured(
            prompt=prompt,
            response_schema=RawAnswerEvaluationResponse,
            system_instruction=system_instruction,
        )

        # Clamp score and confidence to [0.0, 1.0]
        clamped_score = max(0.0, min(1.0, float(raw_eval.score)))
        clamped_conf = max(0.0, min(1.0, float(raw_eval.confidence)))
        is_correct = clamped_score >= 0.75

        eval_id = self.generate_evaluation_id(
            question_id=question.question_id,
            concept_id=question.concept_id,
            student_response=submission,
        )

        return EvaluationResult(
            evaluation_id=eval_id,
            question_id=question.question_id,
            concept_id=question.concept_id,
            correctness=is_correct,
            score=clamped_score,
            confidence=clamped_conf,
            expected_answer=question.correct_answer,
            student_answer=submission,
            concepts_tested=raw_eval.concepts_tested or [question.learning_objective],
            concepts_demonstrated=raw_eval.concepts_demonstrated,
            concepts_missing=raw_eval.concepts_missing,
            reasoning_assessment=raw_eval.reasoning_assessment,
            evidence=raw_eval.evidence,
            feedback=raw_eval.feedback,
        )


# Singleton service instance
answer_evaluator = AnswerEvaluator()
