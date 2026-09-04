import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import (
    InvalidQuestionError,
    InvalidQuestionTypeError,
    QuestionGenerationError,
)
from app.core.gemini import gemini_client
from app.schemas.assessment import (
    Question,
    QuestionType,
    RawGeneratedQuestion,
    RawQuestionBatchResponse,
)
from app.schemas.lesson import Concept, DifficultyLevel, Lesson
from app.schemas.material import DocumentChunk

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Domain service for generating and validating pedagogical assessment questions."""

    def __init__(self, client=None):
        self._gemini_client = client or gemini_client

    # ----------------------------------------------------------------
    # Deterministic Identifiers
    # ----------------------------------------------------------------

    @staticmethod
    def generate_question_id(
        concept_id: str,
        question_type: str,
        question_text: str,
        lesson_id: Optional[str] = None,
    ) -> str:
        """Generate a deterministic SHA-256 question ID from concept, type, text, and lesson."""
        if not question_text or not question_text.strip():
            raise InvalidQuestionError("Cannot generate question ID for empty question text.")
        if not concept_id or not concept_id.strip():
            raise InvalidQuestionError("Cannot generate question ID without a valid concept_id.")

        norm_text = re.sub(r"\s+", " ", question_text.strip().lower())
        q_type = question_type.strip().lower()
        l_id = lesson_id.strip() if lesson_id else "none"

        seed = f"{concept_id}:{l_id}:{q_type}:{norm_text}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"qst_{digest}"

    # ----------------------------------------------------------------
    # Question Validation
    # ----------------------------------------------------------------

    @staticmethod
    def validate_question(question: Question) -> None:
        """Validate structural, pedagogical, and format constraints for a Question."""
        if not question.question_text or not question.question_text.strip():
            raise InvalidQuestionError("Question text cannot be empty or whitespace.")
        if not question.concept_id or not question.concept_id.strip():
            raise InvalidQuestionError("Question must have a valid concept_id.")
        if not question.learning_objective or not question.learning_objective.strip():
            raise InvalidQuestionError("Question must specify a measurable learning_objective.")
        if not question.correct_answer or not question.correct_answer.strip():
            raise InvalidQuestionError("Question must specify a non-empty correct_answer.")
        if not question.explanation or not question.explanation.strip():
            raise InvalidQuestionError("Question must include an explanation.")

        if not isinstance(question.question_type, QuestionType):
            raise InvalidQuestionTypeError(f"Invalid question type: {question.question_type}")

        # MCQ-specific constraints
        if question.question_type == QuestionType.MCQ:
            if len(question.options) < 2:
                raise InvalidQuestionError("MCQ questions must contain at least 2 distinct options.")
            
            # Check unique options
            norm_options = [opt.strip().lower() for opt in question.options]
            if len(norm_options) != len(set(norm_options)):
                raise InvalidQuestionError("MCQ options must be distinct and non-duplicate.")

            # Ensure correct answer matches one of the options (either exact match or letter/index prefix)
            clean_correct = question.correct_answer.strip().lower()
            matches = [opt for opt in question.options if opt.strip().lower() == clean_correct]
            if not matches:
                # Also allow matching if correct_answer is 'A', 'B', etc. or option starts with letter
                matched_by_prefix = False
                for idx, opt in enumerate(question.options):
                    letter = chr(65 + idx)  # A, B, C, D
                    if clean_correct == letter.lower() or opt.strip().lower().startswith(f"{clean_correct})"):
                        matched_by_prefix = True
                        break
                if not matched_by_prefix:
                    raise InvalidQuestionError(
                        f"MCQ correct_answer '{question.correct_answer}' does not match any of the provided options: {question.options}"
                    )

    # ----------------------------------------------------------------
    # Single Question Generation
    # ----------------------------------------------------------------

    async def generate_question(
        self,
        concept: Concept,
        question_type: Optional[QuestionType] = None,
        learning_objective: Optional[str] = None,
        lesson_id: Optional[str] = None,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> Question:
        """Generate a single validated question for a concept."""
        q_type = question_type or QuestionType.CONCEPTUAL
        questions = await self.generate_questions(
            concept=concept,
            count=1,
            question_types=[q_type],
            learning_objective=learning_objective,
            lesson_id=lesson_id,
            source_chunks=source_chunks,
        )
        if not questions:
            raise QuestionGenerationError(f"Failed to generate question for concept '{concept.name}'.")
        return questions[0]

    # ----------------------------------------------------------------
    # Batch Question Generation
    # ----------------------------------------------------------------

    async def generate_questions(
        self,
        concept: Concept,
        count: int = 3,
        question_types: Optional[List[QuestionType]] = None,
        learning_objective: Optional[str] = None,
        lesson_id: Optional[str] = None,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> List[Question]:
        """Generate a diverse batch of validated questions for a concept."""
        if not concept:
            raise InvalidQuestionError("Concept cannot be None.")
        if not concept.concept_id or not concept.name:
            raise InvalidQuestionError("Concept must have a valid concept_id and name.")
        if count <= 0:
            return []

        target_types = question_types or [
            QuestionType.MCQ,
            QuestionType.SHORT_ANSWER,
            QuestionType.CONCEPTUAL,
            QuestionType.APPLICATION,
        ]

        target_objective = (
            learning_objective
            or (concept.learning_objectives[0] if concept.learning_objectives else f"Explain the core principles of {concept.name}.")
        )

        is_grounded = bool(concept.source_chunk_ids)
        grounded_context_str = ""
        material_ids: List[str] = []

        if is_grounded and source_chunks:
            chunk_texts = []
            for chk in source_chunks:
                if chk.chunk_id in concept.source_chunk_ids or not concept.source_chunk_ids:
                    chunk_texts.append(f"[{chk.chunk_id}]: {chk.text}")
                    if chk.material_id and chk.material_id not in material_ids:
                        material_ids.append(chk.material_id)
            if chunk_texts:
                grounded_context_str = "Source Material Chunks:\n" + "\n\n".join(chunk_texts)

        type_names = ", ".join([t.value for t in target_types])
        system_instruction = (
            "You are an expert pedagogical assessment designer for an AI Teacher system.\n"
            f"Generate exactly {count} distinct assessment questions for the concept '{concept.name}'.\n\n"
            f"Target Question Types: {type_names}\n"
            f"Concept Description: {concept.description}\n"
            f"Learning Objective: {target_objective}\n"
            f"Concept Difficulty: {concept.difficulty.value}\n\n"
            "Rules:\n"
            "1. Focus directly on assessing the specified learning objective and concept.\n"
            "2. For MCQ questions:\n"
            "   - Provide 3 to 4 distinct, plausible options.\n"
            "   - Exactly ONE option must be completely correct.\n"
            "   - The 'correct_answer' field must match the correct option text verbatim.\n"
            "3. For Short Answer, Conceptual, or Application questions, options must be empty.\n"
            "4. Provide a clear pedagogical explanation and rubric for evaluation.\n"
            "5. Avoid trivia or superficial wording changes. Test true conceptual understanding."
        )

        prompt = (
            f"Generate {count} assessment questions for:\n"
            f"Concept: {concept.name}\n"
            f"Difficulty: {concept.difficulty.value}\n"
            f"Objective: {target_objective}\n"
        )
        if grounded_context_str:
            prompt += f"\n{grounded_context_str}\n\nStrictly ground questions in the provided text."
        else:
            prompt += "\nThis is a topic-only assessment (no source documents)."

        raw_response = await self._gemini_client.generate_structured(
            prompt=prompt,
            response_schema=RawQuestionBatchResponse,
            system_instruction=system_instruction,
        )

        validated_questions: List[Question] = []
        seen_texts: Set[str] = set()

        for raw_q in raw_response.questions:
            clean_text = raw_q.question_text.strip()
            norm_key = re.sub(r"\s+", " ", clean_text.lower())
            if norm_key in seen_texts:
                continue
            seen_texts.add(norm_key)

            q_id = self.generate_question_id(
                concept_id=concept.concept_id,
                question_type=raw_q.question_type.value,
                question_text=clean_text,
                lesson_id=lesson_id,
            )

            # Determine source IDs strictly according to grounding rules
            q_chunk_ids = list(concept.source_chunk_ids) if is_grounded else []
            q_material_ids = list(material_ids) if is_grounded else []

            # Clean options for non-MCQ
            options = raw_q.options if raw_q.question_type == QuestionType.MCQ else []

            question_obj = Question(
                question_id=q_id,
                question_type=raw_q.question_type,
                question_text=clean_text,
                concept_id=concept.concept_id,
                lesson_id=lesson_id,
                difficulty=raw_q.difficulty or concept.difficulty,
                learning_objective=raw_q.learning_objective or target_objective,
                options=options,
                correct_answer=raw_q.correct_answer.strip(),
                explanation=raw_q.explanation.strip(),
                evaluation_rubric=raw_q.evaluation_rubric,
                source_chunk_ids=q_chunk_ids,
                source_material_ids=q_material_ids,
            )

            try:
                self.validate_question(question_obj)
                validated_questions.append(question_obj)
            except InvalidQuestionError as e:
                logger.warning(f"Generated question failed validation, skipping: {e}")

        if not validated_questions:
            raise QuestionGenerationError(f"All generated questions for concept '{concept.name}' failed validation.")

        return validated_questions

    # ----------------------------------------------------------------
    # Lesson-Level Question Generation
    # ----------------------------------------------------------------

    async def generate_questions_for_lesson(
        self,
        lesson: Lesson,
        concepts: List[Concept],
        count_per_concept: int = 2,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> List[Question]:
        """Generate a complete set of questions assessing all concepts inside a Lesson."""
        if not lesson:
            raise InvalidQuestionError("Lesson cannot be None.")
        if not concepts:
            raise InvalidQuestionError("Concepts list cannot be empty.")

        concept_map = {c.concept_id: c for c in concepts}
        lesson_questions: List[Question] = []

        for c_id in lesson.concept_ids:
            if c_id not in concept_map:
                continue
            concept = concept_map[c_id]
            questions = await self.generate_questions(
                concept=concept,
                count=count_per_concept,
                lesson_id=lesson.lesson_id,
                source_chunks=source_chunks,
            )
            lesson_questions.extend(questions)

        return lesson_questions


# Singleton service instance
question_generator = QuestionGenerator()
