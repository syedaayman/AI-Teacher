import pytest
from pydantic import ValidationError

from app.core.exceptions import (
    AdaptiveEngineError,
    InvalidAdaptationDecisionError,
    InvalidDifficultyTransitionError,
    InvalidMasteryInputError,
    MissingConceptError,
)
from app.schemas.adaptive import (
    AdaptationAction,
    AdaptationDecision,
    ConceptMastery,
    MasteryLevel,
)
from app.schemas.assessment import (
    EvaluationResult,
    Misconception,
    MisconceptionAnalysis,
    MisconceptionSeverity,
)
from app.schemas.lesson import Concept, ConceptGraph, DifficultyLevel
from app.services.adaptive_engine import AdaptiveEngine
from app.services.mastery_engine import MasteryEngine


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def mastery_engine_instance():
    """MasteryEngine instance."""
    return MasteryEngine()


@pytest.fixture
def adaptive_engine_instance():
    """AdaptiveEngine instance."""
    return AdaptiveEngine()


@pytest.fixture
def sample_concept_graph():
    """Create sample 3-node concept graph: Arrays -> Sorting -> Binary Search."""
    c_arrays = Concept(
        concept_id="cpt_arrays_001",
        name="Arrays",
        description="Linear array memory allocation.",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Define contiguous array memory."],
    )
    c_sorting = Concept(
        concept_id="cpt_sorting_002",
        name="Sorting",
        description="Ordering elements in an array.",
        difficulty=DifficultyLevel.BEGINNER,
        learning_objectives=["Explain array ordering."],
        prerequisite_concept_ids=["cpt_arrays_001"],
    )
    c_binsearch = Concept(
        concept_id="cpt_binsearch_101",
        name="Binary Search",
        description="Halving search interval in sorted arrays.",
        difficulty=DifficultyLevel.INTERMEDIATE,
        learning_objectives=["Explain binary search."],
        prerequisite_concept_ids=["cpt_sorting_002"],
    )
    return ConceptGraph(concepts=[c_arrays, c_sorting, c_binsearch])


# ====================================================================
# A. Mastery Tests
# ====================================================================

def test_01_first_attempt_uses_score_directly(mastery_engine_instance):
    """Verify first attempt sets mastery_score exactly equal to evaluation score."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_01",
        correctness=True,
        score=0.85,
        confidence=0.9,
        expected_answer="A",
        student_answer="A",
        evidence="Match",
        feedback="Great",
    )
    mastery = mastery_engine_instance.update_mastery("cpt_01", eval_res, previous_mastery=None)
    assert mastery.mastery_score == 0.85
    assert mastery.attempts == 1
    assert mastery.correct_attempts == 1
    assert mastery.incorrect_attempts == 0
    assert mastery.partial_attempts == 0
    assert mastery.mastery_level == MasteryLevel.PROFICIENT


def test_02_repeated_mastery_uses_weighted_formula(mastery_engine_instance):
    """Verify repeated attempts use formula: 0.6 * previous + 0.4 * current."""
    prev_mastery = ConceptMastery(
        concept_id="cpt_01",
        mastery_score=0.50,
        mastery_level=MasteryLevel.DEVELOPING,
        confidence=0.7,
        attempts=1,
        correct_attempts=0,
        incorrect_attempts=0,
        partial_attempts=1,
        last_score=0.50,
    )
    eval_res = EvaluationResult(
        evaluation_id="eval_02",
        question_id="qst_01",
        concept_id="cpt_01",
        correctness=True,
        score=1.0,
        confidence=1.0,
        expected_answer="A",
        student_answer="A",
        evidence="Match",
        feedback="Great",
    )
    # Expected: 0.6 * 0.50 + 0.4 * 1.0 = 0.30 + 0.40 = 0.70
    updated = mastery_engine_instance.update_mastery("cpt_01", eval_res, previous_mastery=prev_mastery)
    assert updated.mastery_score == 0.70
    assert updated.attempts == 2
    assert updated.correct_attempts == 1
    assert updated.partial_attempts == 1
    assert updated.mastery_level == MasteryLevel.DEVELOPING


def test_03_mastery_is_bounded_0_to_1():
    """Verify ConceptMastery model schema enforces 0.0 to 1.0 bounds."""
    # Valid bounds
    m = ConceptMastery(
        concept_id="cpt_01",
        mastery_score=1.0,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.5,
        attempts=1,
        correct_attempts=1,
    )
    assert 0.0 <= m.mastery_score <= 1.0

    # Invalid score > 1.0
    with pytest.raises(ValidationError):
        ConceptMastery(
            concept_id="cpt_01",
            mastery_score=1.2,
            mastery_level=MasteryLevel.MASTERED,
            confidence=0.5,
        )

    # Invalid score < 0.0
    with pytest.raises(ValidationError):
        ConceptMastery(
            concept_id="cpt_01",
            mastery_score=-0.1,
            mastery_level=MasteryLevel.NOT_STARTED,
            confidence=0.5,
        )


def test_04_all_five_mastery_levels(mastery_engine_instance):
    """Verify threshold mappings for all five canonical MasteryLevel brackets."""
    assert mastery_engine_instance.calculate_mastery_level(0.10) == MasteryLevel.NOT_STARTED
    assert mastery_engine_instance.calculate_mastery_level(0.19) == MasteryLevel.NOT_STARTED
    assert mastery_engine_instance.calculate_mastery_level(0.20) == MasteryLevel.EMERGING
    assert mastery_engine_instance.calculate_mastery_level(0.49) == MasteryLevel.EMERGING
    assert mastery_engine_instance.calculate_mastery_level(0.50) == MasteryLevel.DEVELOPING
    assert mastery_engine_instance.calculate_mastery_level(0.74) == MasteryLevel.DEVELOPING
    assert mastery_engine_instance.calculate_mastery_level(0.75) == MasteryLevel.PROFICIENT
    assert mastery_engine_instance.calculate_mastery_level(0.89) == MasteryLevel.PROFICIENT
    assert mastery_engine_instance.calculate_mastery_level(0.90) == MasteryLevel.MASTERED
    assert mastery_engine_instance.calculate_mastery_level(1.00) == MasteryLevel.MASTERED


def test_05_attempt_statistics_tracking(mastery_engine_instance):
    """Verify correct, incorrect, and partial attempt counters increment appropriately."""
    eval_incorrect = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_01",
        correctness=False,
        score=0.1,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Wrong",
        feedback="No",
    )
    m1 = mastery_engine_instance.update_mastery("cpt_01", eval_incorrect, previous_mastery=None)
    assert m1.attempts == 1
    assert m1.incorrect_attempts == 1
    assert m1.correct_attempts == 0

    eval_partial = EvaluationResult(
        evaluation_id="eval_02",
        question_id="qst_01",
        concept_id="cpt_01",
        correctness=False,
        score=0.5,
        confidence=0.9,
        expected_answer="A",
        student_answer="Partial",
        evidence="Partial",
        feedback="Half",
    )
    m2 = mastery_engine_instance.update_mastery("cpt_01", eval_partial, previous_mastery=m1)
    assert m2.attempts == 2
    assert m2.incorrect_attempts == 1
    assert m2.partial_attempts == 1
    assert m2.correct_attempts == 0


def test_08_invalid_mastery_inputs(mastery_engine_instance):
    """Verify InvalidMasteryInputError on invalid scores or empty concept IDs."""
    with pytest.raises(InvalidMasteryInputError):
        mastery_engine_instance.calculate_mastery_level(1.5)

    with pytest.raises(InvalidMasteryInputError):
        mastery_engine_instance.update_mastery("   ", None)  # type: ignore


# ====================================================================
# B. Difficulty Transition Tests
# ====================================================================

def test_09_difficulty_increase_transitions():
    """Verify valid upward difficulty transitions and cap at advanced."""
    assert AdaptiveEngine.increase_difficulty(DifficultyLevel.BEGINNER) == DifficultyLevel.INTERMEDIATE
    assert AdaptiveEngine.increase_difficulty(DifficultyLevel.INTERMEDIATE) == DifficultyLevel.ADVANCED

    with pytest.raises(InvalidDifficultyTransitionError):
        AdaptiveEngine.increase_difficulty(DifficultyLevel.ADVANCED)


def test_12_difficulty_decrease_transitions():
    """Verify valid downward difficulty transitions and floor at beginner."""
    assert AdaptiveEngine.decrease_difficulty(DifficultyLevel.ADVANCED) == DifficultyLevel.INTERMEDIATE
    assert AdaptiveEngine.decrease_difficulty(DifficultyLevel.INTERMEDIATE) == DifficultyLevel.BEGINNER

    with pytest.raises(InvalidDifficultyTransitionError):
        AdaptiveEngine.decrease_difficulty(DifficultyLevel.BEGINNER)


# ====================================================================
# C. Misconception Priority Tests
# ====================================================================

def test_16_prerequisite_misconception_highest_priority(adaptive_engine_instance, sample_concept_graph):
    """Verify prerequisite misconception triggers REVIEW_PREREQUISITE with prerequisite target."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",
        correctness=False,
        score=0.1,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Misunderstands sorting",
        feedback="Review sorting",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.20,
        mastery_level=MasteryLevel.EMERGING,
        confidence=0.5,
        attempts=1,
        incorrect_attempts=1,
    )
    misc_analysis = MisconceptionAnalysis(
        detected=True,
        misconceptions=[
            Misconception(
                misconception_id="msc_sort_01",
                concept_id="cpt_binsearch_101",
                description="Lacks understanding of sorting invariant.",
                evidence="Claimed binary search works without sorted order.",
                severity=MisconceptionSeverity.HIGH,
                confidence=0.88,
                affected_concept_ids=["cpt_sorting_002"],  # Affects prerequisite!
                source_question_id="qst_01",
            )
        ],
        summary="Prerequisite misunderstanding.",
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        misconception_analysis=misc_analysis,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.REVIEW_PREREQUISITE
    assert decision.target_concept_id == "cpt_sorting_002"  # Targets prerequisite
    assert "cpt_sorting_002" in decision.reason
    assert "msc_sort_01" in decision.misconception_ids


def test_18_conceptual_misconception_triggers_remediation(adaptive_engine_instance, sample_concept_graph):
    """Verify genuine conceptual misconception triggers REMEDIATE_MISCONCEPTION on current concept."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",
        correctness=False,
        score=0.25,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Flawed halving model",
        feedback="Review halving",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.25,
        mastery_level=MasteryLevel.EMERGING,
        confidence=0.5,
        attempts=1,
        incorrect_attempts=1,
    )
    misc_analysis = MisconceptionAnalysis(
        detected=True,
        misconceptions=[
            Misconception(
                misconception_id="msc_cpt_01",
                concept_id="cpt_binsearch_101",
                description="Believes binary search scans both halves simultaneously.",
                evidence="Stated both halves are checked in parallel.",
                severity=MisconceptionSeverity.HIGH,
                confidence=0.85,
                affected_concept_ids=["cpt_binsearch_101"],  # Current concept only
                source_question_id="qst_01",
            )
        ],
        summary="Conceptual misunderstanding.",
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        misconception_analysis=misc_analysis,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.REMEDIATE_MISCONCEPTION
    assert decision.target_concept_id == "cpt_binsearch_101"


def test_20_empty_or_low_confidence_misconception_ignored(adaptive_engine_instance, sample_concept_graph):
    """Verify detected=False or low-confidence misconception (<0.7) does not trigger remediation."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",
        correctness=False,
        score=0.5,
        confidence=0.9,
        expected_answer="A",
        student_answer="Partial",
        evidence="Partial",
        feedback="Half",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.50,
        mastery_level=MasteryLevel.DEVELOPING,
        confidence=0.5,
        attempts=1,
        partial_attempts=1,
    )
    # Misconception with low confidence (0.4)
    misc_analysis = MisconceptionAnalysis(
        detected=True,
        misconceptions=[
            Misconception(
                misconception_id="msc_weak",
                concept_id="cpt_binsearch_101",
                description="Possible minor confusion.",
                evidence="Vague evidence.",
                severity=MisconceptionSeverity.LOW,
                confidence=0.40,  # Below actionable threshold 0.70
                source_question_id="qst_01",
            )
        ],
        summary="Weak signal.",
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        misconception_analysis=misc_analysis,
        concept_graph=sample_concept_graph,
    )

    # Should fall through to partial understanding -> RETRY_QUESTION
    assert decision.action == AdaptationAction.RETRY_QUESTION


# ====================================================================
# D. Performance & Adaptation Rules
# ====================================================================

def test_23_repeated_failure_decreases_difficulty(adaptive_engine_instance, sample_concept_graph):
    """Verify repeated failure decreases difficulty from intermediate to beginner."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",
        correctness=False,
        score=0.10,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Wrong",
        feedback="No",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.20,
        mastery_level=MasteryLevel.EMERGING,
        confidence=0.8,
        attempts=3,
        incorrect_attempts=2,  # Repeated failures
        last_score=0.10,
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.DECREASE_DIFFICULTY
    assert decision.target_difficulty == DifficultyLevel.BEGINNER


def test_24_repeated_failure_at_beginner_triggers_reteach(adaptive_engine_instance, sample_concept_graph):
    """Verify repeated failure at beginner difficulty triggers RETEACH_CONCEPT."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_arrays_001",
        correctness=False,
        score=0.10,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Wrong",
        feedback="No",
    )
    mastery = ConceptMastery(
        concept_id="cpt_arrays_001",
        mastery_score=0.15,
        mastery_level=MasteryLevel.NOT_STARTED,
        confidence=0.8,
        attempts=2,
        incorrect_attempts=2,
        last_score=0.10,
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.BEGINNER,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.RETEACH_CONCEPT
    assert decision.target_difficulty == DifficultyLevel.BEGINNER


def test_27_strong_beginner_increases_difficulty(adaptive_engine_instance, sample_concept_graph):
    """Verify strong performance at BEGINNER increases difficulty to INTERMEDIATE."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_arrays_001",
        correctness=True,
        score=0.95,
        confidence=0.95,
        expected_answer="A",
        student_answer="A",
        evidence="Perfect",
        feedback="Great",
    )
    mastery = ConceptMastery(
        concept_id="cpt_arrays_001",
        mastery_score=0.95,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.6,
        attempts=1,
        correct_attempts=1,
        last_score=0.95,
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.BEGINNER,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.INCREASE_DIFFICULTY
    assert decision.target_difficulty == DifficultyLevel.INTERMEDIATE


def test_29_advanced_mastered_advances_concept(adaptive_engine_instance, sample_concept_graph):
    """Verify mastery at ADVANCED difficulty triggers ADVANCE_CONCEPT to next topological concept."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_arrays_001",
        correctness=True,
        score=1.0,
        confidence=1.0,
        expected_answer="A",
        student_answer="A",
        evidence="Mastered",
        feedback="Great",
    )
    mastery = ConceptMastery(
        concept_id="cpt_arrays_001",
        mastery_score=0.92,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.9,
        attempts=3,
        correct_attempts=3,
        last_score=1.0,
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.ADVANCED,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )

    assert decision.action == AdaptationAction.ADVANCE_CONCEPT
    assert decision.target_concept_id == "cpt_sorting_002"  # Next in graph!


# ====================================================================
# E. Decision Integrity & Determinism
# ====================================================================

def test_33_deterministic_decision_ids():
    """Verify identical parameters produce exact same decision_id."""
    id1 = AdaptiveEngine.generate_decision_id(
        current_concept_id="cpt_01",
        action="increase_difficulty",
        target_concept_id="cpt_01",
        target_difficulty="intermediate",
        mastery_score=0.85,
        learner_id="usr_01",
        session_id="ses_01",
    )
    id2 = AdaptiveEngine.generate_decision_id(
        current_concept_id="cpt_01",
        action="INCREASE_DIFFICULTY",
        target_concept_id="cpt_01",
        target_difficulty="INTERMEDIATE",
        mastery_score=0.85,
        learner_id="usr_01",
        session_id="ses_01",
    )
    assert id1.startswith("adt_")
    assert id1 == id2


def test_35_decision_explanation_and_evidence_populated(adaptive_engine_instance, sample_concept_graph):
    """Verify reason, evidence, and confidence are cleanly populated."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_arrays_001",
        correctness=True,
        score=0.85,
        confidence=0.9,
        expected_answer="A",
        student_answer="A",
        evidence="Good",
        feedback="Good",
    )
    mastery = ConceptMastery(
        concept_id="cpt_arrays_001",
        mastery_score=0.85,
        mastery_level=MasteryLevel.PROFICIENT,
        confidence=0.6,
        attempts=1,
        correct_attempts=1,
    )

    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.BEGINNER,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )

    assert len(decision.reason) > 10
    assert len(decision.evidence) >= 1
    assert 0.0 <= decision.confidence <= 1.0


def test_25_low_mastery_causes_retry_on_first_attempt(adaptive_engine_instance, sample_concept_graph):
    """Verify first attempt with low score causes retry rather than premature reteach."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_arrays_001",
        correctness=False,
        score=0.40,
        confidence=0.9,
        expected_answer="A",
        student_answer="B",
        evidence="Wrong",
        feedback="No",
    )
    mastery = ConceptMastery(
        concept_id="cpt_arrays_001",
        mastery_score=0.40,
        mastery_level=MasteryLevel.EMERGING,
        confidence=0.5,
        attempts=1,
        incorrect_attempts=0,
        partial_attempts=1,
        last_score=0.40,
    )
    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.BEGINNER,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )
    assert decision.action == AdaptationAction.RETRY_QUESTION
    assert decision.target_concept_id == "cpt_arrays_001"


def test_28_strong_intermediate_increases_to_advanced(adaptive_engine_instance, sample_concept_graph):
    """Verify strong performance at INTERMEDIATE increases difficulty to ADVANCED."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",
        correctness=True,
        score=0.90,
        confidence=0.95,
        expected_answer="A",
        student_answer="A",
        evidence="Great",
        feedback="Great",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.90,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.7,
        attempts=1,
        correct_attempts=1,
        last_score=0.90,
    )
    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )
    assert decision.action == AdaptationAction.INCREASE_DIFFICULTY
    assert decision.target_difficulty == DifficultyLevel.ADVANCED


def test_32_no_next_concept_keeps_current_concept(adaptive_engine_instance, sample_concept_graph):
    """Verify advance on last concept in topological order retains current_concept_id as target."""
    eval_res = EvaluationResult(
        evaluation_id="eval_01",
        question_id="qst_01",
        concept_id="cpt_binsearch_101",  # Last concept in 3-node graph
        correctness=True,
        score=1.0,
        confidence=1.0,
        expected_answer="A",
        student_answer="A",
        evidence="Mastered",
        feedback="Mastered",
    )
    mastery = ConceptMastery(
        concept_id="cpt_binsearch_101",
        mastery_score=0.95,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.9,
        attempts=3,
        correct_attempts=3,
        last_score=1.0,
    )
    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_binsearch_101",
        current_difficulty=DifficultyLevel.ADVANCED,
        evaluation_result=eval_res,
        concept_mastery=mastery,
        concept_graph=sample_concept_graph,
    )
    assert decision.action == AdaptationAction.ADVANCE_CONCEPT
    assert decision.target_concept_id == "cpt_binsearch_101"


def test_36_end_to_end_assessment_to_adaptation_pipeline(adaptive_engine_instance, mastery_engine_instance, sample_concept_graph):
    """Verify full deterministic pipeline from EvaluationResult -> MasteryEngine -> AdaptiveEngine."""
    eval_res = EvaluationResult(
        evaluation_id="eval_e2e_01",
        question_id="qst_e2e_01",
        concept_id="cpt_arrays_001",
        correctness=True,
        score=0.88,
        confidence=0.92,
        expected_answer="Option A",
        student_answer="Option A",
        evidence="Accurate definition provided.",
        feedback="Well done!",
    )

    # 1. Update concept mastery
    updated_mastery = mastery_engine_instance.update_mastery(
        concept_id="cpt_arrays_001",
        evaluation_result=eval_res,
        previous_mastery=None,
    )
    assert updated_mastery.mastery_score == 0.88
    assert updated_mastery.mastery_level == MasteryLevel.PROFICIENT

    # 2. Derive adaptation decision
    decision = adaptive_engine_instance.decide_next_action(
        current_concept_id="cpt_arrays_001",
        current_difficulty=DifficultyLevel.BEGINNER,
        evaluation_result=eval_res,
        concept_mastery=updated_mastery,
        concept_graph=sample_concept_graph,
        learner_id="student_42",
        session_id="session_101",
    )

    assert decision.action == AdaptationAction.INCREASE_DIFFICULTY
    assert decision.target_difficulty == DifficultyLevel.INTERMEDIATE
    assert decision.target_concept_id == "cpt_arrays_001"
    assert decision.learner_id == "student_42"
    assert decision.session_id == "session_101"
    assert decision.decision_id.startswith("adt_")
