import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import (
    AnswerEvaluationError,
    EmptyAnswerError,
    InvalidQuestionError,
    InvalidQuestionTypeError,
    MisconceptionDetectionError,
    QuestionGenerationError,
)
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
    Question,
    QuestionType,
    RawAnswerEvaluationResponse,
    RawGeneratedQuestion,
    RawMisconceptionDetectionResponse,
    RawMisconceptionItem,
    RawQuestionBatchResponse,
    StudentAnswer,
)
from app.schemas.lesson import Concept, DifficultyLevel, Lesson
from app.schemas.material import DocumentChunk
from app.services.answer_evaluator import AnswerEvaluator
from app.services.misconception_detector import MisconceptionDetector
from app.services.question_generator import QuestionGenerator


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client with structured response capability."""
    client = MagicMock()
    client.is_configured = True
    client.generate_structured = AsyncMock()
    return client


@pytest.fixture
def sample_concept():
    """Create sample material-grounded concept."""
    return Concept(
        concept_id="cpt_binsearch_101",
        name="Binary Search",
        description="Divide-and-conquer algorithm for finding an element in a sorted array by repeatedly halving the search interval.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objectives=[
            "Explain the divide-and-conquer principle of binary search.",
            "Trace binary search on a sorted array.",
            "Analyze the O(log n) time complexity of binary search.",
        ],
        prerequisite_concept_ids=["cpt_arrays_001", "cpt_sorting_002"],
        related_concept_ids=["cpt_linearsearch_003"],
        source_chunk_ids=["chk_algo_01", "chk_algo_02"],
        source_metadata={"filename": "algorithms.pdf"},
    )


@pytest.fixture
def sample_topic_concept():
    """Create sample ungrounded topic-only concept."""
    return Concept(
        concept_id="cpt_quantum_001",
        name="Qubit Superposition",
        description="Principle of quantum superposition where a quantum state exists as a linear combination of basis states.",
        difficulty=DifficultyLevel.ADVANCED,
        learning_objectives=[
            "Define quantum superposition.",
            "Calculate probability amplitudes for basic quantum states.",
        ],
        prerequisite_concept_ids=[],
        related_concept_ids=[],
        source_chunk_ids=[],
        source_metadata={},
    )


@pytest.fixture
def sample_lesson(sample_concept):
    """Create sample Lesson."""
    return Lesson(
        lesson_id="lsn_search_algorithms",
        title="Searching Algorithms",
        description="Introduction to linear and binary search algorithms.",
        concept_ids=[sample_concept.concept_id],
        learning_objectives=sample_concept.learning_objectives,
        difficulty=DifficultyLevel.INTERMEDIATE,
        estimated_duration_minutes=45,
        sequence_index=0,
        source_material_ids=["mat_algo_101"],
    )


@pytest.fixture
def sample_chunks():
    """Sample document chunks."""
    return [
        DocumentChunk(
            chunk_id="chk_algo_01",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=0,
            text="Binary search requires the array to be sorted. It compares the target with the middle element.",
            page_number=10,
        ),
        DocumentChunk(
            chunk_id="chk_algo_02",
            material_id="mat_algo_101",
            filename="algorithms.pdf",
            file_type="pdf",
            chunk_index=1,
            text="In each step, binary search eliminates half of the remaining elements, yielding O(log n) time complexity.",
            page_number=11,
        ),
    ]


# ====================================================================
# 1. Question Schemas & Determinism
# ====================================================================

def test_01_question_schema_validation():
    """Verify Question model field defaults and validation."""
    q = Question(
        question_id="qst_1234567890abcdef",
        question_type=QuestionType.MCQ,
        question_text="What is the time complexity of binary search?",
        concept_id="cpt_binsearch_101",
        lesson_id="lsn_01",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objective="Analyze the O(log n) time complexity.",
        options=["O(1)", "O(log n)", "O(n)", "O(n^2)"],
        correct_answer="O(log n)",
        explanation="Binary search cuts the search space in half each iteration.",
        source_chunk_ids=["chk_01"],
        source_material_ids=["mat_01"],
    )
    assert q.question_id == "qst_1234567890abcdef"
    assert q.question_type == QuestionType.MCQ
    assert len(q.options) == 4
    assert q.correct_answer == "O(log n)"


def test_02_deterministic_question_ids():
    """Verify identical parameters produce exact same question_id and ignore transient factors."""
    id1 = QuestionGenerator.generate_question_id(
        concept_id="cpt_binsearch_101",
        question_type="mcq",
        question_text="What is binary search?",
        lesson_id="lsn_01",
    )
    id2 = QuestionGenerator.generate_question_id(
        concept_id="cpt_binsearch_101",
        question_type="MCQ",
        question_text="  what is binary search?  ",
        lesson_id="lsn_01",
    )
    id3 = QuestionGenerator.generate_question_id(
        concept_id="cpt_binsearch_101",
        question_type="short_answer",
        question_text="What is binary search?",
        lesson_id="lsn_01",
    )
    assert id1.startswith("qst_")
    assert id1 == id2  # Case & whitespace normalized
    assert id1 != id3  # Different question type produces different ID


# ====================================================================
# 2. Question Generation & Diversity
# ====================================================================

@pytest.mark.asyncio
async def test_03_mcq_generation(sample_concept, mock_gemini_client):
    """Test generating valid multiple choice questions."""
    mock_gemini_client.generate_structured.return_value = RawQuestionBatchResponse(
        questions=[
            RawGeneratedQuestion(
                question_type=QuestionType.MCQ,
                question_text="Why must the input array be sorted for binary search?",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objective="Explain the divide-and-conquer principle of binary search.",
                options=[
                    "To allow elements to be checked sequentially",
                    "To determine which half of the array contains the target",
                    "To reduce memory usage to O(1)",
                    "To ensure all elements are positive",
                ],
                correct_answer="To determine which half of the array contains the target",
                explanation="Without sorted order, comparing with the middle element provides no information about where the target lies.",
            )
        ]
    )

    generator = QuestionGenerator(client=mock_gemini_client)
    questions = await generator.generate_questions(
        concept=sample_concept,
        count=1,
        question_types=[QuestionType.MCQ],
    )

    assert len(questions) == 1
    q = questions[0]
    assert q.question_type == QuestionType.MCQ
    assert len(q.options) == 4
    assert q.correct_answer in q.options
    assert q.concept_id == sample_concept.concept_id


@pytest.mark.asyncio
async def test_04_short_answer_and_conceptual_generation(sample_concept, mock_gemini_client):
    """Test short-answer, conceptual, and application question generation."""
    mock_gemini_client.generate_structured.return_value = RawQuestionBatchResponse(
        questions=[
            RawGeneratedQuestion(
                question_type=QuestionType.SHORT_ANSWER,
                question_text="State the recurrence relation for the time complexity of binary search.",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objective="Analyze the O(log n) time complexity.",
                options=[],
                correct_answer="T(n) = T(n/2) + O(1)",
                explanation="Each step takes constant time and halves the input size.",
            ),
            RawGeneratedQuestion(
                question_type=QuestionType.APPLICATION,
                question_text="Given array [2, 5, 8, 12, 16, 23, 38, 56, 72, 91], trace the indices inspected when searching for 23.",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objective="Trace binary search on a sorted array.",
                options=[],
                correct_answer="Middle index 4 (value 16), then middle index 7 (value 56), then middle index 5 (value 23).",
                explanation="Step 1: mid=4 (16 < 23), Step 2: mid=7 (56 > 23), Step 3: mid=5 (23 == 23).",
            ),
        ]
    )

    generator = QuestionGenerator(client=mock_gemini_client)
    questions = await generator.generate_questions(
        concept=sample_concept,
        count=2,
        question_types=[QuestionType.SHORT_ANSWER, QuestionType.APPLICATION],
    )

    assert len(questions) == 2
    assert questions[0].question_type == QuestionType.SHORT_ANSWER
    assert questions[0].options == []
    assert questions[1].question_type == QuestionType.APPLICATION
    assert questions[1].options == []


@pytest.mark.asyncio
async def test_07_material_grounded_traceability(sample_concept, sample_chunks, mock_gemini_client):
    """Test material-grounded question retains chunk and material IDs."""
    mock_gemini_client.generate_structured.return_value = RawQuestionBatchResponse(
        questions=[
            RawGeneratedQuestion(
                question_type=QuestionType.CONCEPTUAL,
                question_text="Explain how binary search halves the search space.",
                difficulty=DifficultyLevel.INTERMEDIATE,
                learning_objective="Explain the divide-and-conquer principle of binary search.",
                options=[],
                correct_answer="By comparing target to middle element and discarding half.",
                explanation="Detailed explanation.",
            )
        ]
    )

    generator = QuestionGenerator(client=mock_gemini_client)
    questions = await generator.generate_questions(
        concept=sample_concept,
        count=1,
        source_chunks=sample_chunks,
    )

    assert len(questions) == 1
    assert questions[0].source_chunk_ids == sample_concept.source_chunk_ids
    assert "mat_algo_101" in questions[0].source_material_ids


@pytest.mark.asyncio
async def test_08_topic_only_question_generation(sample_topic_concept, mock_gemini_client):
    """Test topic-only question has strictly empty source chunk and material IDs."""
    mock_gemini_client.generate_structured.return_value = RawQuestionBatchResponse(
        questions=[
            RawGeneratedQuestion(
                question_type=QuestionType.CONCEPTUAL,
                question_text="What does a state vector represent in quantum superposition?",
                difficulty=DifficultyLevel.ADVANCED,
                learning_objective="Define quantum superposition.",
                options=[],
                correct_answer="A linear combination of basis vectors in Hilbert space.",
                explanation="Superposition is represented as a state vector.",
            )
        ]
    )

    generator = QuestionGenerator(client=mock_gemini_client)
    questions = await generator.generate_questions(concept=sample_topic_concept, count=1)

    assert len(questions) == 1
    assert questions[0].source_chunk_ids == []
    assert questions[0].source_material_ids == []


# ====================================================================
# 3. Question Validation & Rejection
# ====================================================================

def test_09_question_validation_success():
    """Verify validate_question passes for a well-formed Question."""
    q = Question(
        question_id="qst_valid",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain recursion base cases.",
        concept_id="cpt_recursion",
        learning_objective="Explain base cases.",
        correct_answer="A condition that terminates recursive calls.",
        explanation="Base cases prevent infinite recursion.",
    )
    QuestionGenerator.validate_question(q)


def test_10_invalid_mcq_rejection():
    """Verify invalid MCQs (missing options, duplicate options, or non-matching correct answer) are rejected."""
    # Fewer than 2 options
    q_few = Question(
        question_id="qst_bad1",
        question_type=QuestionType.MCQ,
        question_text="Question text?",
        concept_id="cpt_01",
        learning_objective="Obj",
        options=["Only one option"],
        correct_answer="Only one option",
        explanation="Explanation",
    )
    with pytest.raises(InvalidQuestionError):
        QuestionGenerator.validate_question(q_few)

    # Correct answer not in options
    q_nomatch = Question(
        question_id="qst_bad2",
        question_type=QuestionType.MCQ,
        question_text="Question text?",
        concept_id="cpt_01",
        learning_objective="Obj",
        options=["Option A", "Option B", "Option C"],
        correct_answer="Option D (Not in list)",
        explanation="Explanation",
    )
    with pytest.raises(InvalidQuestionError):
        QuestionGenerator.validate_question(q_nomatch)


# ====================================================================
# 4. Answer Evaluation (Deterministic MCQ & Semantic Open-Ended)
# ====================================================================

@pytest.mark.asyncio
async def test_13_correct_mcq_evaluation():
    """Verify deterministic evaluation of correct MCQ answer."""
    question = Question(
        question_id="qst_mcq_01",
        question_type=QuestionType.MCQ,
        question_text="What is 2 + 2?",
        concept_id="cpt_math",
        learning_objective="Perform basic arithmetic.",
        options=["2", "3", "4", "5"],
        correct_answer="4",
        explanation="2 + 2 equals 4.",
    )
    answer = StudentAnswer(
        question_id="qst_mcq_01",
        selected_option="4",
    )

    evaluator = AnswerEvaluator()
    result = await evaluator.evaluate_answer(question, answer)

    assert result.correctness is True
    assert result.score == 1.0
    assert result.confidence == 1.0
    assert "matches the correct answer" in result.evidence
    assert result.evaluation_id.startswith("eval_")


@pytest.mark.asyncio
async def test_14_incorrect_mcq_evaluation():
    """Verify deterministic evaluation of incorrect MCQ answer."""
    question = Question(
        question_id="qst_mcq_01",
        question_type=QuestionType.MCQ,
        question_text="What is 2 + 2?",
        concept_id="cpt_math",
        learning_objective="Perform basic arithmetic.",
        options=["2", "3", "4", "5"],
        correct_answer="4",
        explanation="2 + 2 equals 4.",
    )
    answer = StudentAnswer(
        question_id="qst_mcq_01",
        selected_option="3",
    )

    evaluator = AnswerEvaluator()
    result = await evaluator.evaluate_answer(question, answer)

    assert result.correctness is False
    assert result.score == 0.0
    assert result.confidence == 1.0
    assert "incorrect" in result.evidence.lower()
    assert result.concepts_missing == ["Perform basic arithmetic."]


@pytest.mark.asyncio
async def test_15_partial_open_ended_evaluation(mock_gemini_client):
    """Verify partial credit evaluation of open-ended conceptual answer."""
    question = Question(
        question_id="qst_open_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain why binary search has O(log n) time complexity.",
        concept_id="cpt_binsearch_101",
        learning_objective="Analyze the O(log n) time complexity.",
        correct_answer="Each comparison divides the remaining array in half, requiring at most log2(n) iterations.",
        explanation="Halving the search space per iteration yields logarithmic steps.",
    )
    answer = StudentAnswer(
        question_id="qst_open_01",
        answer_text="It is fast because it divides the list.",
        reasoning="I remembered it divides things.",
    )

    mock_gemini_client.generate_structured.return_value = RawAnswerEvaluationResponse(
        score=0.5,
        confidence=0.9,
        concepts_tested=["Divide-and-conquer", "Logarithmic complexity"],
        concepts_demonstrated=["Division of search space"],
        concepts_missing=["Log2(n) relationship to array length", "Halving search space at each iteration"],
        reasoning_assessment="Recognizes division but omits the mathematical link to logarithmic iterations.",
        evidence="Student states 'divides the list' without specifying halving or logarithmic scaling.",
        feedback="Good recognition that the list is divided! Remember that halving the list each step gives log2(n) steps.",
    )

    evaluator = AnswerEvaluator(client=mock_gemini_client)
    result = await evaluator.evaluate_answer(question, answer)

    assert result.score == 0.5
    assert result.correctness is False  # score < 0.75
    assert result.confidence == 0.9
    assert len(result.concepts_demonstrated) == 1
    assert len(result.concepts_missing) == 2
    assert "Good recognition" in result.feedback


@pytest.mark.asyncio
async def test_16_fully_correct_open_ended_evaluation(mock_gemini_client):
    """Verify high-scoring evaluation for comprehensive student answer."""
    question = Question(
        question_id="qst_open_02",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain why binary search requires a sorted array.",
        concept_id="cpt_binsearch_101",
        learning_objective="Explain the divide-and-conquer principle of binary search.",
        correct_answer="The algorithm compares the target with the middle element and assumes all elements to the left are smaller and all to the right are larger. If unsorted, it cannot safely discard half of the array.",
        explanation="Sorted order is the invariant that allows half the search space to be discarded.",
    )
    answer = StudentAnswer(
        question_id="qst_open_02",
        answer_text="Because binary search checks the middle item. If the target is smaller, it only knows the target is in the left half if all left items are smaller than the middle.",
    )

    mock_gemini_client.generate_structured.return_value = RawAnswerEvaluationResponse(
        score=1.0,
        confidence=0.95,
        concepts_tested=["Sorted array invariant"],
        concepts_demonstrated=["Sorted array invariant", "Search space elimination"],
        concepts_missing=[],
        reasoning_assessment="Accurate deduction of the sorted invariant.",
        evidence="Clearly explains that left-half elimination depends on sorted order.",
        feedback="Excellent and complete explanation!",
    )

    evaluator = AnswerEvaluator(client=mock_gemini_client)
    result = await evaluator.evaluate_answer(question, answer)

    assert result.score == 1.0
    assert result.correctness is True
    assert result.concepts_missing == []


# ====================================================================
# 5. Misconception Detection
# ====================================================================

def test_21_misconception_schema_validation():
    """Verify Misconception model attributes and enum validation."""
    m = Misconception(
        misconception_id="msc_12345678",
        concept_id="cpt_binsearch_101",
        description="Believes binary search works on unsorted arrays by sorting on the fly.",
        evidence="Student stated 'it sorts each half first'.",
        severity=MisconceptionSeverity.HIGH,
        confidence=0.88,
        affected_concept_ids=["cpt_binsearch_101", "cpt_sorting_002"],
        source_question_id="qst_01",
        recommended_focus="Clarify preprocessing requirements for binary search.",
    )
    assert m.misconception_id == "msc_12345678"
    assert m.severity == MisconceptionSeverity.HIGH
    assert len(m.affected_concept_ids) == 2


@pytest.mark.asyncio
async def test_22_genuine_misconception_detection(mock_gemini_client):
    """Test diagnosing a genuine conceptual misunderstanding."""
    question = Question(
        question_id="qst_bs_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="How does binary search find a target?",
        concept_id="cpt_binsearch_101",
        learning_objective="Explain binary search.",
        correct_answer="Repeatedly halves the sorted search interval.",
        explanation="Binary search halves the array.",
    )
    student_answer = StudentAnswer(
        question_id="qst_bs_01",
        answer_text="Binary search checks every item one by one from left to right until it finds the target.",
    )
    eval_result = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_bs_01",
        concept_id="cpt_binsearch_101",
        correctness=False,
        score=0.1,
        confidence=0.9,
        expected_answer=question.correct_answer,
        student_answer=student_answer.answer_text,
        concepts_tested=["Binary search mechanism"],
        concepts_demonstrated=[],
        concepts_missing=["Divide-and-conquer", "Halving interval"],
        evidence="Student described linear search instead of binary search.",
        feedback="This describes linear search.",
    )

    mock_gemini_client.generate_structured.return_value = RawMisconceptionDetectionResponse(
        is_genuine_misconception=True,
        misconceptions=[
            RawMisconceptionItem(
                description="Confuses binary search with linear/sequential search.",
                evidence="Described checking every item one by one from left to right.",
                severity=MisconceptionSeverity.HIGH,
                confidence=0.92,
                is_prerequisite_flaw=False,
                recommended_focus="Contrast linear scan O(n) with binary halving O(log n).",
            )
        ],
        summary="Student confuses binary search with sequential scan.",
    )

    detector = MisconceptionDetector(client=mock_gemini_client)
    analysis = await detector.detect_misconceptions(
        question=question,
        student_answer=student_answer,
        evaluation_result=eval_result,
    )

    assert isinstance(analysis, MisconceptionAnalysis)
    assert analysis.detected is True
    assert len(analysis.misconceptions) == 1
    m = analysis.misconceptions[0]
    assert m.misconception_id.startswith("msc_")
    assert m.severity == MisconceptionSeverity.HIGH
    assert m.confidence == 0.92


@pytest.mark.asyncio
async def test_23_simple_slip_not_classified_as_misconception(mock_gemini_client):
    """Verify simple typos or arithmetic slips are not classified as misconceptions."""
    question = Question(
        question_id="qst_math_01",
        question_type=QuestionType.SHORT_ANSWER,
        question_text="Compute 15 / 3.",
        concept_id="cpt_division",
        learning_objective="Division",
        correct_answer="5",
        explanation="15 divided by 3 is 5.",
    )
    student_answer = StudentAnswer(
        question_id="qst_math_01",
        answer_text="5.01",  # Typo
    )
    eval_result = EvaluationResult(
        evaluation_id="eval_02",
        question_id="qst_math_01",
        concept_id="cpt_division",
        correctness=False,
        score=0.7,
        confidence=0.9,
        expected_answer="5",
        student_answer="5.01",
        concepts_tested=["Division"],
        concepts_demonstrated=["Division"],
        concepts_missing=["Exact precision"],
        evidence="Student typed 5.01 instead of 5.",
        feedback="Check your typing precision.",
    )

    mock_gemini_client.generate_structured.return_value = RawMisconceptionDetectionResponse(
        is_genuine_misconception=False,
        misconceptions=[],
        summary="Minor typographical slip.",
    )

    detector = MisconceptionDetector(client=mock_gemini_client)
    analysis = await detector.detect_misconceptions(
        question=question,
        student_answer=student_answer,
        evaluation_result=eval_result,
    )

    assert analysis.detected is False
    assert analysis.misconceptions == []


@pytest.mark.asyncio
async def test_24_prerequisite_misconception_detection(sample_concept, mock_gemini_client):
    """Verify prerequisite flaw diagnosis populates affected prerequisite concept IDs."""
    question = Question(
        question_id="qst_bs_02",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Why does binary search fail if elements are not ordered?",
        concept_id=sample_concept.concept_id,
        learning_objective="Explain binary search preconditions.",
        correct_answer="Because ordering is required to know which half to discard.",
        explanation="Sorted order is essential.",
    )
    student_answer = StudentAnswer(
        question_id="qst_bs_02",
        answer_text="Arrays cannot store numbers in ascending order without pointers.",
    )
    eval_result = EvaluationResult(
        evaluation_id="eval_03",
        question_id=question.question_id,
        concept_id=question.concept_id,
        correctness=False,
        score=0.0,
        confidence=0.9,
        expected_answer=question.correct_answer,
        student_answer=student_answer.answer_text,
        concepts_tested=["Array ordering"],
        concepts_demonstrated=[],
        concepts_missing=["Basic array indexing and ordering"],
        evidence="Shows fundamental misunderstanding of array memory and ordering.",
        feedback="Review basic array data structures.",
    )

    mock_gemini_client.generate_structured.return_value = RawMisconceptionDetectionResponse(
        is_genuine_misconception=True,
        misconceptions=[
            RawMisconceptionItem(
                description="Misunderstands how contiguous array memory supports sorted ordering.",
                evidence="Claimed arrays need pointers to be sorted.",
                severity=MisconceptionSeverity.HIGH,
                confidence=0.9,
                is_prerequisite_flaw=True,  # Flaw in prerequisite 'cpt_arrays_001'
                recommended_focus="Review array data structure foundations.",
            )
        ],
        summary="Prerequisite misunderstanding in arrays.",
    )

    detector = MisconceptionDetector(client=mock_gemini_client)
    analysis = await detector.detect_misconceptions(
        question=question,
        student_answer=student_answer,
        evaluation_result=eval_result,
        concept=sample_concept,
    )

    assert analysis.detected is True
    assert len(analysis.misconceptions) == 1
    m = analysis.misconceptions[0]
    # Verify prerequisite concept IDs are included in affected concepts
    assert "cpt_arrays_001" in m.affected_concept_ids


@pytest.mark.asyncio
async def test_28_no_misconception_for_fully_correct_answer():
    """Verify perfect 1.0 answer bypasses LLM and immediately returns detected=False."""
    question = Question(
        question_id="qst_perf",
        question_type=QuestionType.MCQ,
        question_text="Q",
        concept_id="cpt_01",
        learning_objective="Obj",
        options=["A", "B"],
        correct_answer="A",
        explanation="Exp",
    )
    answer = StudentAnswer(question_id="qst_perf", selected_option="A")
    eval_result = EvaluationResult(
        evaluation_id="eval_perf",
        question_id="qst_perf",
        concept_id="cpt_01",
        correctness=True,
        score=1.0,
        confidence=1.0,
        expected_answer="A",
        student_answer="A",
        concepts_tested=["Obj"],
        concepts_demonstrated=["Obj"],
        concepts_missing=[],
        evidence="Exact match",
        feedback="Correct!",
    )

    detector = MisconceptionDetector()
    analysis = await detector.detect_misconceptions(question, answer, eval_result)
    assert analysis.detected is False
    assert analysis.misconceptions == []


# ====================================================================
# 6. Integration & Error Handling
# ====================================================================

@pytest.mark.asyncio
async def test_30_end_to_end_assessment_pipeline(sample_concept, mock_gemini_client):
    """End-to-end pipeline: Concept -> Question -> StudentAnswer -> Evaluation -> MisconceptionAnalysis."""
    # 1. Question Generator response
    mock_gemini_client.generate_structured.side_effect = [
        RawQuestionBatchResponse(
            questions=[
                RawGeneratedQuestion(
                    question_type=QuestionType.CONCEPTUAL,
                    question_text="Explain the time complexity of binary search.",
                    difficulty=DifficultyLevel.INTERMEDIATE,
                    learning_objective="Analyze O(log n) time complexity.",
                    options=[],
                    correct_answer="O(log n) because the search space is halved every iteration.",
                    explanation="Halving yields log2(n) steps.",
                )
            ]
        ),
        # 2. Answer Evaluator response
        RawAnswerEvaluationResponse(
            score=0.25,
            confidence=0.88,
            concepts_tested=["Logarithmic complexity"],
            concepts_demonstrated=[],
            concepts_missing=["Halving search interval"],
            reasoning_assessment="Flawed model assuming search takes linear time proportional to all elements.",
            evidence="Student claims search time doubles as array size doubles.",
            feedback="Remember that doubling the array only adds 1 extra step.",
        ),
        # 3. Misconception Detector response
        RawMisconceptionDetectionResponse(
            is_genuine_misconception=True,
            misconceptions=[
                RawMisconceptionItem(
                    description="Believes doubling search space doubles binary search execution time.",
                    evidence="Student claims time doubles with array size.",
                    severity=MisconceptionSeverity.MEDIUM,
                    confidence=0.85,
                    is_prerequisite_flaw=False,
                    recommended_focus="Demonstrate that doubling n adds only 1 step in binary search.",
                )
            ],
            summary="Linear scaling misconception on logarithmic algorithm.",
        ),
    ]

    q_gen = QuestionGenerator(client=mock_gemini_client)
    evaluator = AnswerEvaluator(client=mock_gemini_client)
    detector = MisconceptionDetector(client=mock_gemini_client)

    # Step 1: Generate question
    questions = await q_gen.generate_questions(concept=sample_concept, count=1)
    assert len(questions) == 1
    question = questions[0]

    # Step 2: Student submits flawed answer
    answer = StudentAnswer(
        question_id=question.question_id,
        answer_text="If you double the array size, binary search takes twice as long.",
    )

    # Step 3: Evaluate answer
    eval_result = await evaluator.evaluate_answer(question, answer)
    assert eval_result.score == 0.25
    assert eval_result.correctness is False

    # Step 4: Detect misconception
    misc_analysis = await detector.detect_misconceptions(question, answer, eval_result, concept=sample_concept)
    assert misc_analysis.detected is True
    assert len(misc_analysis.misconceptions) == 1
    assert misc_analysis.misconceptions[0].source_evaluation_id == eval_result.evaluation_id


@pytest.mark.asyncio
async def test_34_empty_answer_rejection():
    """Verify empty or whitespace student answer raises EmptyAnswerError."""
    question = Question(
        question_id="qst_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Q",
        concept_id="cpt_01",
        learning_objective="Obj",
        correct_answer="Ans",
        explanation="Exp",
    )
    answer = StudentAnswer(question_id="qst_01", answer_text="   ")

    evaluator = AnswerEvaluator()
    with pytest.raises(EmptyAnswerError):
        await evaluator.evaluate_answer(question, answer)


@pytest.mark.asyncio
async def test_35_question_answer_mismatch_rejection():
    """Verify mismatch between question_id and answer.question_id raises AnswerEvaluationError."""
    question = Question(
        question_id="qst_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Q",
        concept_id="cpt_01",
        learning_objective="Obj",
        correct_answer="Ans",
        explanation="Exp",
    )
    answer = StudentAnswer(question_id="qst_DIFFERENT", answer_text="Some answer")

    evaluator = AnswerEvaluator()
    with pytest.raises(AnswerEvaluationError):
        await evaluator.evaluate_answer(question, answer)


@pytest.mark.asyncio
async def test_11_duplicate_question_prevention(sample_concept, mock_gemini_client):
    """Verify generator deduplicates identical question texts returned in a batch."""
    mock_gemini_client.generate_structured.return_value = RawQuestionBatchResponse(
        questions=[
            RawGeneratedQuestion(
                question_type=QuestionType.CONCEPTUAL,
                question_text="What is binary search?",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objective="Define binary search.",
                options=[],
                correct_answer="A search algorithm.",
                explanation="Explanation",
            ),
            RawGeneratedQuestion(  # Duplicate question text
                question_type=QuestionType.CONCEPTUAL,
                question_text="  what is binary search?  ",
                difficulty=DifficultyLevel.BEGINNER,
                learning_objective="Define binary search.",
                options=[],
                correct_answer="A search algorithm.",
                explanation="Explanation",
            ),
        ]
    )
    generator = QuestionGenerator(client=mock_gemini_client)
    questions = await generator.generate_questions(concept=sample_concept, count=2)
    assert len(questions) == 1  # Deduplicated to 1


def test_12_student_answer_validation():
    """Verify StudentAnswer validation and defaults."""
    ans = StudentAnswer(
        question_id="qst_01",
        answer_text="My response",
        reasoning="My logic",
    )
    assert ans.question_id == "qst_01"
    assert ans.answer_text == "My response"
    assert ans.submitted_at is not None


@pytest.mark.asyncio
async def test_17_incorrect_open_ended_evaluation(mock_gemini_client):
    """Verify completely incorrect open-ended answer produces score 0.0 and correctness False."""
    question = Question(
        question_id="qst_01",
        question_type=QuestionType.CONCEPTUAL,
        question_text="Explain photosynthesis.",
        concept_id="cpt_bio",
        learning_objective="Photosynthesis",
        correct_answer="Light conversion to chemical energy.",
        explanation="Explanation",
    )
    answer = StudentAnswer(
        question_id="qst_01",
        answer_text="It is when rocks melt in a volcano.",
    )
    mock_gemini_client.generate_structured.return_value = RawAnswerEvaluationResponse(
        score=0.0,
        confidence=1.0,
        concepts_tested=["Photosynthesis"],
        concepts_demonstrated=[],
        concepts_missing=["Light absorption", "Chemical energy"],
        reasoning_assessment="Irrelevant answer describing volcanology.",
        evidence="Student described volcanic rock melting.",
        feedback="This is incorrect. Photosynthesis occurs in plants to convert light into sugars.",
    )
    evaluator = AnswerEvaluator(client=mock_gemini_client)
    result = await evaluator.evaluate_answer(question, answer)

    assert result.score == 0.0
    assert result.correctness is False
    assert len(result.concepts_missing) == 2


def test_18_evaluation_score_bounds():
    """Verify EvaluationResult strictly enforces score and confidence bounds [0.0, 1.0]."""
    # Valid score
    res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_01",
        correctness=True,
        score=0.85,
        confidence=0.95,
        expected_answer="A",
        student_answer="A",
        evidence="Match",
        feedback="Great",
    )
    assert 0.0 <= res.score <= 1.0
    assert 0.0 <= res.confidence <= 1.0

    # Invalid score > 1.0
    with pytest.raises(ValidationError):
        EvaluationResult(
            evaluation_id="eval_02",
            question_id="qst_01",
            concept_id="cpt_01",
            correctness=True,
            score=1.5,
            expected_answer="A",
            student_answer="A",
            evidence="Match",
            feedback="Great",
        )

    # Invalid score < 0.0
    with pytest.raises(ValidationError):
        EvaluationResult(
            evaluation_id="eval_03",
            question_id="qst_01",
            concept_id="cpt_01",
            correctness=False,
            score=-0.2,
            expected_answer="A",
            student_answer="A",
            evidence="Match",
            feedback="Great",
        )


def test_27_deterministic_misconception_ids():
    """Verify deterministic misconception IDs ignore whitespace and case."""
    id1 = MisconceptionDetector.generate_misconception_id("cpt_01", "qst_01", "Confuses linear and binary search")
    id2 = MisconceptionDetector.generate_misconception_id("cpt_01", "qst_01", "  confuses linear and binary search  ")
    id3 = MisconceptionDetector.generate_misconception_id("cpt_02", "qst_01", "Confuses linear and binary search")

    assert id1.startswith("msc_")
    assert id1 == id2
    assert id1 != id3


@pytest.mark.asyncio
async def test_36_invalid_concept_parameter_rejection():
    """Verify invalid or empty concepts raise InvalidQuestionError."""
    generator = QuestionGenerator()
    with pytest.raises(InvalidQuestionError):
        await generator.generate_questions(concept=None)  # type: ignore
