import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import (
    InvalidQuestionError,
    InvalidQuestionTypeError,
    LLMQuotaExceededError,
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
    # Deterministic High-Quality Fallback Generation
    # ----------------------------------------------------------------

    @staticmethod
    def _generate_fallback_questions(
        concept: Concept,
        question_types: Optional[List[QuestionType]] = None,
        count: int = 3,
        lesson_id: Optional[str] = None,
        target_objective: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Question]:
        """Generate structured, high-quality deterministic fallback questions dynamically.

        Generates both MCQ and short-answer questions tailored to the concept name and difficulty level.
        Formats the response to match the exact schema returned by the LLM, including options,
        correct_answer_index, explanation, and misconception hints.
        """
        if count <= 0:
            return []

        c_name = getattr(concept, "name", None) or "Core Concept"
        c_id = getattr(concept, "concept_id", None) or "cpt_fallback"
        raw_desc = getattr(concept, "description", None) or ""
        desc = raw_desc.strip() if raw_desc else f"principles, characteristics, and application of {c_name}"
        desc_summary = desc[:150] + ("..." if len(desc) > 150 else "")

        difficulty = getattr(concept, "difficulty", DifficultyLevel.BEGINNER)
        if not isinstance(difficulty, DifficultyLevel):
            try:
                difficulty = DifficultyLevel(str(difficulty).lower())
            except Exception:
                difficulty = DifficultyLevel.BEGINNER

        obj = (
            target_objective
            or (concept.learning_objectives[0] if getattr(concept, "learning_objectives", None) else None)
            or f"Demonstrate sound understanding of {c_name} at the {difficulty.value} level."
        )

        chunk_ids = list(getattr(concept, "source_chunk_ids", []) or [])

        # Filter target question types
        supported_types = [
            QuestionType.MCQ,
            QuestionType.SHORT_ANSWER,
            QuestionType.CONCEPTUAL,
            QuestionType.APPLICATION,
        ]
        chosen_types = [qt for qt in (question_types or supported_types) if qt in supported_types]
        if not chosen_types:
            chosen_types = [QuestionType.MCQ, QuestionType.SHORT_ANSWER]

        # ------------------------------------------------------------
        # Pedagogical question templates segmented by difficulty level
        # ------------------------------------------------------------
        if difficulty == DifficultyLevel.ADVANCED:
            mcq_pool = [
                {
                    "text": f"In large-scale or concurrent architectures, what primary challenge arises when coordinating {c_name} across distributed nodes?",
                    "options": [
                        f"Preserving state consistency, cache coherency, and synchronization invariants under high concurrency.",
                        f"Preventing distributed nodes from rejecting standard network protocols due to {c_name}.",
                        f"Compensating for hardware clock drift by eliminating all timestamps completely.",
                        f"Overcoming arbitrary bit flips that occur exclusively when {c_name} is invoked.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Advanced systems require rigorous concurrency management, cache coherency, and synchronization invariants when {c_name} is involved ({desc_summary}).",
                    "misconceptions": [
                        f"Overlooking race conditions and synchronization boundaries in distributed deployments of {c_name}.",
                        f"Attributing concurrency contention to mythical hardware-level failures.",
                    ],
                    "rubric": "Full credit for identifying state consistency, cache coherency, and concurrency invariants.",
                },
                {
                    "text": f"How should an enterprise architecture design fault tolerance for critical service paths relying on {c_name}?",
                    "options": [
                        f"By employing circuit breakers, idempotent retry semantics, and graceful degradation strategies around {c_name}.",
                        f"By allowing faults in {c_name} to cascade unabated through all upstream consumers.",
                        f"By restarting the entire cluster whenever any single {c_name} operation encounters latency.",
                        f"By disabling telemetry and logging to prevent throughput degradation during failure states.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Resilient architecture demands circuit breaking, idempotency, and graceful fallback to isolate faults in {c_name}.",
                    "misconceptions": [
                        f"Assuming {c_name} self-heals without defensive isolation patterns.",
                        f"Using destructive cluster-wide restarts instead of bounded component recovery.",
                    ],
                    "rubric": "Award credit for selecting idempotent retries, circuit breaking, and defensive isolation.",
                },
                {
                    "text": f"Which asymptotic or algorithmic characteristic limits the maximum throughput of {c_name} under extreme workload?",
                    "options": [
                        f"Contention on shared mutable state, memory allocation overhead, and non-linear complexity bottlenecks.",
                        f"The absolute physical speed of electrons in standard copper cabling.",
                        f"An arbitrary restriction in modern operating systems to 256 variables.",
                        f"A fundamental incompatibility between {c_name} and modern 64-bit multi-core CPUs.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Under extreme loads, {c_name} scalability is constrained by algorithmic complexity, memory bandwidth, and contention on shared state.",
                    "misconceptions": [
                        f"Ignoring synchronization contention and memory limits when evaluating bottlenecks in {c_name}.",
                        f"Attributing software scalability ceilings to arbitrary hardware incompatibilities.",
                    ],
                    "rubric": "Credit for identifying shared-state contention and algorithmic scaling constraints.",
                },
            ]
            short_pool = [
                {
                    "text": f"Analyze the primary failure modes of {c_name} under high concurrency and propose defensive architectural patterns to mitigate them.",
                    "correct_answer": f"Under high concurrency, {c_name} risks race conditions, deadlocks, or state inconsistency. Mitigation requires lock-free primitives, idempotent operations, and transactional boundaries.",
                    "explanation": f"Advanced analysis requires diagnosing concurrency failure modes and implementing robust isolation patterns for {c_name} ({desc_summary}).",
                    "misconceptions": [
                        f"Assuming {c_name} is inherently thread-safe without explicit synchronization.",
                        f"Proposing global locks that create unscalable systemic bottlenecks.",
                    ],
                    "rubric": "Award full credit for correctly diagnosing concurrency risks (race conditions/deadlocks) and proposing concrete mitigation (idempotency, lock-free structures, or circuit breaking).",
                },
                {
                    "text": f"How would you optimize {c_name} for latency-critical environments without compromising its fundamental correctness invariants?",
                    "correct_answer": f"Optimization requires minimizing heap allocations, pre-computing static invariants, using vectorized or zero-copy primitives, and caching verified results while preserving correctness in {c_name}.",
                    "explanation": f"Optimizing {c_name} demands strategic resource efficiency while strictly preserving algorithmic invariants.",
                    "misconceptions": [
                        f"Suggesting aggressive optimizations that violate correctness or data integrity invariants.",
                        f"Focusing on trivial micro-optimizations outside the execution critical path.",
                    ],
                    "rubric": "Credit for proposing zero-copy, allocation reduction, or caching while maintaining correctness invariants.",
                },
                {
                    "text": f"Discuss the security and data-integrity implications of exposing {c_name} to untrusted external inputs.",
                    "correct_answer": f"Untrusted inputs interacting with {c_name} can induce resource exhaustion (DoS), deserialization exploits, or invalid state transitions. Mitigation requires strict input sanitization, rate limiting, and defensive bounds checking.",
                    "explanation": f"System security demands validating, sanitizing, and bounding all external access points to {c_name}.",
                    "misconceptions": [
                        f"Assuming internal components using {c_name} are inherently safe from malicious payloads.",
                        f"Overlooking resource exhaustion and denial-of-service attack vectors.",
                    ],
                    "rubric": "Credit for identifying DoS/integrity risks and stating concrete defenses (validation, rate-limiting, bounds checking).",
                },
            ]
        elif difficulty == DifficultyLevel.INTERMEDIATE:
            mcq_pool = [
                {
                    "text": f"When implementing or applying {c_name}, which operational consideration is most critical for ensuring correctness?",
                    "options": [
                        f"Validating input preconditions and systematically handling boundary conditions for {c_name}.",
                        f"Assuming all incoming data adheres to ideal invariants without validation.",
                        f"Suppressing all runtime exceptions to maintain an illusion of error-free operation.",
                        f"Assuming {c_name} guarantees O(1) performance across all input distributions regardless of state.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Intermediate application of {c_name} requires defensive validation of preconditions and boundary limits ({desc_summary}).",
                    "misconceptions": [
                        f"Assuming {c_name} handles arbitrary invalid input automatically without validation.",
                        f"Believing {c_name} guarantees constant time complexity in all contexts.",
                    ],
                    "rubric": "Full credit for selecting precondition validation and boundary condition handling.",
                },
                {
                    "text": f"What is the characteristic engineering trade-off encountered when integrating {c_name} into a system?",
                    "options": [
                        f"Balancing structural or computational setup overhead against enhanced clarity, control, and efficiency in {c_name}.",
                        f"Trading all persistent data security for a negligible boost in loop iteration speed.",
                        f"Mandating that every concurrent worker thread execute without thread-safety synchronization.",
                        f"Permanently preventing the host application from performing any persistent I/O operations.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Applying {c_name} involves balanced trade-offs between implementation overhead and operational guarantees ({desc_summary}).",
                    "misconceptions": [
                        f"Believing {c_name} has no architectural trade-offs or overhead.",
                        f"Assuming {c_name} prevents basic system operations like persistent I/O.",
                    ],
                    "rubric": "Credit for identifying genuine trade-offs between coordination overhead and operational benefits.",
                },
                {
                    "text": f"How does {c_name} maintain predictable execution when encountering non-standard or edge-case inputs?",
                    "options": [
                        f"By evaluating deterministic guards and executing defined fallback or termination branches.",
                        f"By mutating inputs randomly until an acceptable state is arbitrarily found.",
                        f"By terminating the operating system process immediately without diagnostic logging.",
                        f"By routing all edge-case inputs into unbounded recursive invocations.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Reliable implementations of {c_name} incorporate deterministic guards and well-defined fallback branches.",
                    "misconceptions": [
                        f"Believing edge cases should be handled via random input mutation.",
                        f"Thinking unhandled crashes or unbounded recursion are acceptable edge-case handlers.",
                    ],
                    "rubric": "Award credit for identifying deterministic guards and defined termination branches.",
                },
            ]
            short_pool = [
                {
                    "text": f"Explain how {c_name} functions internally and identify one key edge case that must be handled.",
                    "correct_answer": f"{c_name} operates by {desc_summary}. A vital edge case involves handling empty inputs, boundary bounds, or unexpected data types gracefully.",
                    "explanation": f"Intermediate proficiency entails understanding internal mechanics and boundary state handling for {c_name}.",
                    "misconceptions": [
                        f"Explaining {c_name} without identifying boundary conditions or edge cases.",
                        f"Misidentifying the internal operational mechanism of {c_name}.",
                    ],
                    "rubric": "Credit for explaining the internal flow and naming at least one valid boundary or edge case.",
                },
                {
                    "text": f"Compare {c_name} with an alternative or naive approach. What specific advantages does it offer?",
                    "correct_answer": f"Compared to naive or unoptimized approaches, {c_name} provides systematic structure, improved predictability, and efficiency as reflected in: {desc_summary}.",
                    "explanation": f"Comparative analysis reveals the engineering rationale and benefits of adopting {c_name}.",
                    "misconceptions": [
                        f"Asserting that {c_name} has no advantage over brute force solutions.",
                        f"Failing to articulate how {c_name} differs from a naive implementation.",
                    ],
                    "rubric": "Award credit for identifying improved structure, predictability, or efficiency over naive alternatives.",
                },
                {
                    "text": f"Describe how you would debug an unexpected invariant violation in a module utilizing {c_name}.",
                    "correct_answer": f"Debugging {c_name} requires inspecting initial preconditions, tracing state transitions, and verifying that the invariants of {c_name} are preserved at each step.",
                    "explanation": f"Systematic debugging requires verifying preconditions and state transitions against the conceptual model of {c_name}.",
                    "misconceptions": [
                        f"Suggesting random trial-and-error code changes without state inspection.",
                        f"Ignoring the core invariants established by {c_name}.",
                    ],
                    "rubric": "Credit for outlining a systematic debugging strategy: inspecting preconditions, tracing transitions, and verifying invariants.",
                },
            ]
        else:  # BEGINNER
            mcq_pool = [
                {
                    "text": f"Which of the following best defines the fundamental concept of {c_name}?",
                    "options": [
                        f"{c_name} is {desc_summary}.",
                        f"{c_name} is an unmonitored hardware process that executes outside the software environment.",
                        f"{c_name} is a deprecated syntax construct with no functional relevance in modern computing.",
                        f"{c_name} is a network packet header used strictly for raw telemetry without computational logic.",
                    ],
                    "correct_index": 0,
                    "explanation": f"Correct! {c_name} fundamentally centers on {desc_summary}. The other choices misstate its scope or describe unrelated constructs.",
                    "misconceptions": [
                        f"Confusing {c_name} with low-level hardware or raw network protocols.",
                        f"Assuming {c_name} is obsolete or lacks operational purpose.",
                    ],
                    "rubric": "Award full credit for selecting the primary definition and scope of {c_name}.",
                },
                {
                    "text": f"What is the primary objective or role of utilizing {c_name}?",
                    "options": [
                        f"To provide a structured and predictable mechanism for {c_name.lower()} operations.",
                        f"To bypass error detection routines and execute unchecked instructions.",
                        f"To eliminate all computational latency and memory consumption completely.",
                        f"To convert all asynchronous workflows into blocking single-threaded loops.",
                    ],
                    "correct_index": 0,
                    "explanation": f"The primary purpose of {c_name} is to establish structured and predictable operations ({desc_summary}).",
                    "misconceptions": [
                        f"Believing {c_name} magically eliminates all computational resource costs.",
                        f"Assuming {c_name} is intended to bypass safety or verification layers.",
                    ],
                    "rubric": "Verify recognition of the purpose and practical bounds of {c_name}.",
                },
                {
                    "text": f"Which core characteristic distinguishes {c_name} from unrelated concepts?",
                    "options": [
                        f"Its direct alignment with {desc_summary}.",
                        f"Its complete independence from computer memory and operating system abstractions.",
                        f"Its ability to execute without any input parameters or contextual state.",
                        f"Its strict restriction to analog signal transformations.",
                    ],
                    "correct_index": 0,
                    "explanation": f"{c_name} is characterized by its pedagogical role in {desc_summary}. The other options misstate its technical dependencies.",
                    "misconceptions": [
                        f"Thinking {c_name} operates without memory or OS state.",
                        f"Misidentifying {c_name} as an analog hardware component.",
                    ],
                    "rubric": "Full credit for recognizing the defining characteristic of {c_name}.",
                },
            ]
            short_pool = [
                {
                    "text": f"In your own words, explain the core idea and significance of {c_name}.",
                    "correct_answer": f"{c_name} is defined as: {desc_summary}. Its significance lies in enabling consistent, well-defined behavior in this domain.",
                    "explanation": f"Foundational mastery of {c_name} requires articulating its definition ({desc_summary}) and recognizing its purpose.",
                    "misconceptions": [
                        f"Giving an overly vague response that fails to mention {c_name}'s purpose.",
                        f"Confusing {c_name} with an unrelated software tool.",
                    ],
                    "rubric": "Student should explain the main definition and state at least one practical purpose.",
                },
                {
                    "text": f"Describe a common real-world situation or scenario where {c_name} is applied.",
                    "correct_answer": f"In practice, {c_name} is applied when {desc_summary} is required, providing systematic organization and reliable outcomes.",
                    "explanation": f"Connecting {c_name} to practical scenarios demonstrates grounded conceptual understanding.",
                    "misconceptions": [
                        f"Selecting a context where {c_name} is not applicable.",
                        f"Describing a trivial scenario with no connection to {c_name}'s definition.",
                    ],
                    "rubric": "Credit for a realistic scenario directly applicable to {c_name}.",
                },
                {
                    "text": f"What basic problem does {c_name} solve for a developer or learner?",
                    "correct_answer": f"{c_name} addresses the challenge of managing {c_name.lower()} by introducing structured handling and clarity as outlined in: {desc_summary}.",
                    "explanation": f"Understanding the underlying problem {c_name} solves clarifies why the concept was created.",
                    "misconceptions": [
                        f"Stating that {c_name} solves unrelated problems like physical storage degradation.",
                        f"Overlooking the core motivation behind {c_name}.",
                    ],
                    "rubric": "Credit for correctly identifying the core motivation and problem solved by {c_name}.",
                },
            ]

        fallback_questions: List[Question] = []
        mcq_idx = 0
        short_idx = 0

        for i in range(count):
            # Alternate or pick according to requested question_types
            desired_type = chosen_types[i % len(chosen_types)]

            if desired_type == QuestionType.MCQ:
                tpl = mcq_pool[mcq_idx % len(mcq_pool)]
                mcq_idx += 1
                q_text = tpl["text"] if i < len(mcq_pool) else f"{tpl['text']} (Perspective {i + 1})"
                options = list(tpl["options"])
                correct_ans = options[tpl["correct_index"]]
                correct_idx = tpl["correct_index"]
                explanation = tpl["explanation"]
                misc_hints = list(tpl["misconceptions"])
                rubric = tpl["rubric"]
                q_type = QuestionType.MCQ
            else:
                tpl = short_pool[short_idx % len(short_pool)]
                short_idx += 1
                q_text = tpl["text"] if i < len(short_pool) else f"{tpl['text']} (Perspective {i + 1})"
                options = []
                correct_ans = tpl["correct_answer"]
                correct_idx = None
                explanation = tpl["explanation"]
                misc_hints = list(tpl["misconceptions"])
                rubric = tpl["rubric"]
                q_type = desired_type if desired_type in [QuestionType.SHORT_ANSWER, QuestionType.CONCEPTUAL, QuestionType.APPLICATION] else QuestionType.SHORT_ANSWER

            q_id = QuestionGenerator.generate_question_id(
                concept_id=c_id,
                question_type=q_type.value,
                question_text=q_text,
                lesson_id=lesson_id,
            )

            q_obj = Question(
                question_id=q_id,
                question_type=q_type,
                question_text=q_text,
                concept_id=c_id,
                lesson_id=lesson_id,
                difficulty=difficulty,
                learning_objective=obj,
                options=options,
                correct_answer=correct_ans,
                correct_answer_index=correct_idx,
                explanation=explanation,
                misconception_hints=misc_hints,
                evaluation_rubric=rubric,
                source_chunk_ids=chunk_ids,
                source_material_ids=[],
            )

            try:
                QuestionGenerator.validate_question(q_obj)
            except Exception as e:
                logger.warning("Deterministic fallback question failed validation unexpectedly: %s", e)

            fallback_questions.append(q_obj)

        return fallback_questions

    # Legacy alias for backward compatibility
    @staticmethod
    def _build_fallback_questions(
        concept: Concept,
        count: int = 3,
        question_types: Optional[List[QuestionType]] = None,
        target_objective: Optional[str] = None,
        lesson_id: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Question]:
        """Backward-compatible alias routing to _generate_fallback_questions."""
        return QuestionGenerator._generate_fallback_questions(
            concept=concept,
            question_types=question_types,
            count=count,
            lesson_id=lesson_id,
            target_objective=target_objective,
            **kwargs,
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
        """Generate a single validated question for a concept.

        Guarantees that a valid Question is returned even during LLM outages or quota limits.
        """
        q_type = question_type or QuestionType.CONCEPTUAL
        try:
            questions = await self.generate_questions(
                concept=concept,
                count=1,
                question_types=[q_type],
                learning_objective=learning_objective,
                lesson_id=lesson_id,
                source_chunks=source_chunks,
            )
            if questions:
                return questions[0]
        except Exception as e:
            logger.warning("generate_question caught exception: %s; invoking fallback", e)

        fallbacks = self._generate_fallback_questions(
            concept=concept,
            question_types=[q_type],
            count=1,
            lesson_id=lesson_id,
            target_objective=learning_objective,
        )
        return fallbacks[0]

    # ----------------------------------------------------------------
    # Internal LLM Generation
    # ----------------------------------------------------------------

    async def _generate_via_llm(
        self,
        concept: Concept,
        count: int = 3,
        question_types: Optional[List[QuestionType]] = None,
        learning_objective: Optional[str] = None,
        lesson_id: Optional[str] = None,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> List[Question]:
        """Internal: call Gemini to generate a batch of validated questions."""
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
            "   - Provide 'correct_answer_index' (0-indexed).\n"
            "   - Provide 'misconception_hints' listing 2 common learner misconceptions targeted by the options.\n"
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

        # Step 1: Wrap Gemini LLM call inside a try/except catching all API, network, and quota errors
        try:
            raw_response = await self._gemini_client.generate_structured(
                prompt=prompt,
                response_schema=RawQuestionBatchResponse,
                system_instruction=system_instruction,
            )
        except Exception as e:
            logger.warning(
                "Gemini LLM call failed for concept '%s' (API/network/quota error): %s",
                concept.name,
                e,
            )
            return []

        if not raw_response or not getattr(raw_response, "questions", None):
            return []

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

            q_chunk_ids = list(concept.source_chunk_ids) if is_grounded else []
            q_material_ids = list(material_ids) if is_grounded else []

            options = raw_q.options if raw_q.question_type == QuestionType.MCQ else []

            # Infer or validate correct_answer_index
            corr_idx = getattr(raw_q, "correct_answer_index", None)
            if corr_idx is None and raw_q.question_type == QuestionType.MCQ and options:
                clean_corr = raw_q.correct_answer.strip().lower()
                for idx, opt in enumerate(options):
                    if opt.strip().lower() == clean_corr:
                        corr_idx = idx
                        break

            misc_hints = getattr(raw_q, "misconception_hints", []) or []

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
                correct_answer_index=corr_idx,
                explanation=raw_q.explanation.strip(),
                misconception_hints=misc_hints,
                evaluation_rubric=raw_q.evaluation_rubric,
                source_chunk_ids=q_chunk_ids,
                source_material_ids=q_material_ids,
            )

            try:
                self.validate_question(question_obj)
                validated_questions.append(question_obj)
            except InvalidQuestionError as e:
                logger.warning("Generated question failed validation, skipping: %s", e)

        return validated_questions

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
        """Generate questions with automatic fallback when Gemini quota is exhausted or API calls fail."""
        if not concept:
            raise InvalidQuestionError("Concept cannot be None.")

        target_types = question_types or [
            QuestionType.MCQ,
            QuestionType.SHORT_ANSWER,
            QuestionType.CONCEPTUAL,
            QuestionType.APPLICATION,
        ]
        target_objective = (
            learning_objective
            or (
                concept.learning_objectives[0]
                if getattr(concept, "learning_objectives", None)
                else f"Explain the core principles of {getattr(concept, 'name', 'the concept')}."
            )
        )

        try:
            questions = await self._generate_via_llm(
                concept=concept,
                count=count,
                question_types=target_types,
                learning_objective=target_objective,
                lesson_id=lesson_id,
                source_chunks=source_chunks,
            )
            if questions:
                return questions
            logger.info(
                "LLM generated 0 valid questions for '%s'; using deterministic fallback",
                getattr(concept, "name", "unknown"),
            )
        except (LLMQuotaExceededError, Exception) as err:
            logger.warning(
                "QuestionGenerator: LLM question generation failed for '%s' (%s); using deterministic fallback",
                getattr(concept, "name", "unknown"),
                err,
            )

        return self._generate_fallback_questions(
            concept=concept,
            question_types=target_types,
            count=count,
            lesson_id=lesson_id,
            target_objective=target_objective,
        )

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
