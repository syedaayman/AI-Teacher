import pytest
from pydantic import ValidationError

from app.core.exceptions import (
    InvalidLearnerProfileError,
    InvalidProfileUpdateError,
    LearnerNotFoundError,
)
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.learner import LearnerProfile, SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.services.learner_profile import LearnerProfileService


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def profile_service():
    """Fresh LearnerProfileService instance with empty store."""
    svc = LearnerProfileService()
    svc.reset_store()
    return svc


# ====================================================================
# A. Profile Creation Tests
# ====================================================================

def test_01_create_valid_profile(profile_service):
    """Verify creating a valid learner profile with all attributes."""
    profile = profile_service.create_profile(
        learner_id="usr_alice_01",
        name="Alice",
        preferred_language=SupportedLanguage.ENGLISH,
        learning_goal="Master Data Structures",
        preferred_difficulty=DifficultyLevel.BEGINNER,
        total_lessons=10,
    )

    assert profile.learner_id == "usr_alice_01"
    assert profile.name == "Alice"
    assert profile.preferred_language == SupportedLanguage.ENGLISH
    assert profile.learning_goal == "Master Data Structures"
    assert profile.preferred_difficulty == DifficultyLevel.BEGINNER
    assert profile.total_lessons == 10
    assert profile.overall_mastery == 0.0
    assert profile.assessment_count == 0
    assert profile.completed_lessons == []


def test_02_reject_empty_learner_id(profile_service):
    """Verify empty or whitespace-only learner IDs are rejected."""
    with pytest.raises(InvalidLearnerProfileError):
        profile_service.create_profile(learner_id="")

    with pytest.raises(InvalidLearnerProfileError):
        profile_service.create_profile(learner_id="   ")


def test_03_default_language_is_english(profile_service):
    """Verify default preferred language is English."""
    profile = profile_service.create_profile(learner_id="usr_bob_02")
    assert profile.preferred_language == SupportedLanguage.ENGLISH


def test_04_default_difficulty_is_intermediate(profile_service):
    """Verify default preferred difficulty is Intermediate."""
    profile = profile_service.create_profile(learner_id="usr_charlie_03")
    assert profile.preferred_difficulty == DifficultyLevel.INTERMEDIATE


def test_05_optional_name_and_goal_handling(profile_service):
    """Verify profile handles optional name and goal when omitted."""
    profile = profile_service.create_profile(learner_id="usr_dave_04")
    assert profile.name is None
    assert profile.learning_goal is None


# ====================================================================
# B. Preferences Tests
# ====================================================================

def test_06_update_language(profile_service):
    """Verify updating preferred language to Hindi or Hinglish."""
    profile_service.create_profile(learner_id="usr_01")

    p_hindi = profile_service.update_preferences(
        learner_id="usr_01",
        preferred_language=SupportedLanguage.HINDI,
    )
    assert p_hindi.preferred_language == SupportedLanguage.HINDI

    p_hinglish = profile_service.update_preferences(
        learner_id="usr_01",
        preferred_language=SupportedLanguage.HINGLISH,
    )
    assert p_hinglish.preferred_language == SupportedLanguage.HINGLISH


def test_07_update_difficulty(profile_service):
    """Verify updating learner's preferred baseline difficulty."""
    profile_service.create_profile(learner_id="usr_01", preferred_difficulty=DifficultyLevel.BEGINNER)

    updated = profile_service.update_preferences(
        learner_id="usr_01",
        preferred_difficulty=DifficultyLevel.ADVANCED,
    )
    assert updated.preferred_difficulty == DifficultyLevel.ADVANCED


def test_08_update_learning_goal(profile_service):
    """Verify updating stated learning curriculum goal."""
    profile_service.create_profile(learner_id="usr_01")
    updated = profile_service.update_learning_goal(
        learner_id="usr_01",
        learning_goal="Prepare for technical interview",
    )
    assert updated.learning_goal == "Prepare for technical interview"


def test_09_reject_unsupported_language(profile_service):
    """Verify unsupported languages raise InvalidProfileUpdateError or InvalidLearnerProfileError."""
    profile_service.create_profile(learner_id="usr_01")

    with pytest.raises(InvalidProfileUpdateError):
        profile_service.update_preferences(learner_id="usr_01", preferred_language="spanish")  # type: ignore

    with pytest.raises(InvalidLearnerProfileError):
        profile_service.create_profile(learner_id="usr_02", preferred_language="french")  # type: ignore


def test_10_reject_invalid_difficulty(profile_service):
    """Verify invalid difficulty levels raise appropriate error."""
    profile_service.create_profile(learner_id="usr_01")

    with pytest.raises(InvalidProfileUpdateError):
        profile_service.update_preferences(learner_id="usr_01", preferred_difficulty="expert")  # type: ignore


# ====================================================================
# C. Mastery Integration Tests
# ====================================================================

def test_11_add_concept_mastery(profile_service):
    """Verify adding ConceptMastery updates profile concept_masteries dictionary."""
    profile_service.create_profile(learner_id="usr_01")

    cm = ConceptMastery(
        concept_id="cpt_arrays",
        mastery_score=0.85,
        mastery_level=MasteryLevel.PROFICIENT,
        confidence=0.9,
        attempts=2,
        correct_attempts=2,
    )
    p = profile_service.update_mastery(learner_id="usr_01", concept_mastery=cm)

    assert "cpt_arrays" in p.concept_masteries
    assert p.concept_masteries["cpt_arrays"].mastery_score == 0.85
    assert p.overall_mastery == 0.85


def test_12_update_existing_concept_mastery(profile_service):
    """Verify subsequent mastery updates cleanly overwrite the concept entry and recalculate."""
    profile_service.create_profile(learner_id="usr_01")

    cm1 = ConceptMastery(
        concept_id="cpt_arrays",
        mastery_score=0.40,
        mastery_level=MasteryLevel.EMERGING,
        confidence=0.5,
        attempts=1,
    )
    profile_service.update_mastery(learner_id="usr_01", concept_mastery=cm1)

    cm2 = ConceptMastery(
        concept_id="cpt_arrays",
        mastery_score=0.95,
        mastery_level=MasteryLevel.MASTERED,
        confidence=0.9,
        attempts=2,
        correct_attempts=1,
    )
    p = profile_service.update_mastery(learner_id="usr_01", concept_mastery=cm2)

    assert p.concept_masteries["cpt_arrays"].mastery_score == 0.95
    assert p.overall_mastery == 0.95
    assert "cpt_arrays" in p.mastered_concepts


def test_14_overall_mastery_calculation(profile_service):
    """Verify overall mastery is calculated as the mean of all concept masteries."""
    profile_service.create_profile(learner_id="usr_01")

    cm1 = ConceptMastery(
        concept_id="cpt_01",
        mastery_score=0.80,
        mastery_level=MasteryLevel.PROFICIENT,
        confidence=0.8,
    )
    cm2 = ConceptMastery(
        concept_id="cpt_02",
        mastery_score=0.60,
        mastery_level=MasteryLevel.DEVELOPING,
        confidence=0.8,
    )
    profile_service.update_mastery("usr_01", cm1)
    p = profile_service.update_mastery("usr_01", cm2)

    # Expected: (0.80 + 0.60) / 2 = 0.70
    assert p.overall_mastery == 0.70


def test_15_overall_mastery_zero_with_no_concepts(profile_service):
    """Verify overall mastery defaults to 0.0 when no concepts are mastered or assessed."""
    p = profile_service.create_profile(learner_id="usr_01")
    assert p.overall_mastery == 0.0


# ====================================================================
# D. Strengths and Weak Areas Tests
# ====================================================================

def test_17_strengths_and_weak_areas_classification(profile_service):
    """Verify PROFICIENT/MASTERED -> strengths, NOT_STARTED/EMERGING -> weak_areas."""
    profile_service.create_profile(learner_id="usr_01")

    cm_prof = ConceptMastery(
        concept_id="cpt_trees",
        mastery_score=0.80,
        mastery_level=MasteryLevel.PROFICIENT,
    )
    cm_mast = ConceptMastery(
        concept_id="cpt_arrays",
        mastery_score=0.95,
        mastery_level=MasteryLevel.MASTERED,
    )
    cm_emerg = ConceptMastery(
        concept_id="cpt_graphs",
        mastery_score=0.30,
        mastery_level=MasteryLevel.EMERGING,
    )
    cm_dev = ConceptMastery(
        concept_id="cpt_dp",
        mastery_score=0.60,
        mastery_level=MasteryLevel.DEVELOPING,
    )

    profile_service.update_mastery("usr_01", cm_prof)
    profile_service.update_mastery("usr_01", cm_mast)
    profile_service.update_mastery("usr_01", cm_emerg)
    p = profile_service.update_mastery("usr_01", cm_dev)

    # Strengths: arrays, trees (sorted)
    assert p.strengths == ["cpt_arrays", "cpt_trees"]
    # Weak areas: graphs
    assert p.weak_areas == ["cpt_graphs"]
    # Mastered concepts: arrays
    assert p.mastered_concepts == ["cpt_arrays"]
    # Active concepts: dp, graphs (developing / emerging)
    assert p.active_concepts == ["cpt_dp", "cpt_graphs"]


def test_20_deterministic_strength_weak_ordering(profile_service):
    """Verify strengths and weak areas lists maintain deterministic alphabetical sort order."""
    profile_service.create_profile(learner_id="usr_01")

    for cid in ["cpt_z", "cpt_a", "cpt_m"]:
        cm = ConceptMastery(
            concept_id=cid,
            mastery_score=0.85,
            mastery_level=MasteryLevel.PROFICIENT,
        )
        profile_service.update_mastery("usr_01", cm)

    p = profile_service.get_profile("usr_01")
    assert p.strengths == ["cpt_a", "cpt_m", "cpt_z"]


# ====================================================================
# E. Lesson Progress Tests
# ====================================================================

def test_22_record_lesson_completion(profile_service):
    """Verify recording completed lesson increments completed list."""
    profile_service.create_profile(learner_id="usr_01", total_lessons=5)

    p = profile_service.record_lesson_completion("usr_01", "lsn_01")
    assert p.completed_lessons == ["lsn_01"]


def test_23_rerecording_same_lesson_does_not_duplicate(profile_service):
    """Verify recording the same completed lesson multiple times maintains idempotency."""
    profile_service.create_profile(learner_id="usr_01", total_lessons=5)

    profile_service.record_lesson_completion("usr_01", "lsn_01")
    p = profile_service.record_lesson_completion("usr_01", "lsn_01")

    assert p.completed_lessons == ["lsn_01"]


# ====================================================================
# F. Assessment Summary Tests
# ====================================================================

def test_26_first_and_subsequent_assessment_averages(profile_service):
    """Verify running average score updates incrementally with each assessment."""
    profile_service.create_profile(learner_id="usr_01")

    # 1st assessment: score = 0.80 -> average = 0.80
    p1 = profile_service.record_assessment_result("usr_01", score=0.80)
    assert p1.assessment_count == 1
    assert p1.average_score == 0.80

    # 2nd assessment: score = 0.60 -> average = (0.80 + 0.60) / 2 = 0.70
    p2 = profile_service.record_assessment_result("usr_01", score=0.60)
    assert p2.assessment_count == 2
    assert p2.average_score == 0.70

    # 3rd assessment: score = 1.00 -> average = (0.70 * 2 + 1.00) / 3 = 2.40 / 3 = 0.80
    p3 = profile_service.record_assessment_result("usr_01", score=1.00)
    assert p3.assessment_count == 3
    assert p3.average_score == 0.80


def test_28_invalid_assessment_score_rejected(profile_service):
    """Verify scores outside 0.0 to 1.0 raise InvalidProfileUpdateError."""
    profile_service.create_profile(learner_id="usr_01")

    with pytest.raises(InvalidProfileUpdateError):
        profile_service.record_assessment_result("usr_01", score=1.5)

    with pytest.raises(InvalidProfileUpdateError):
        profile_service.record_assessment_result("usr_01", score=-0.1)


# ====================================================================
# G. Architecture & Boundary Tests
# ====================================================================

def test_30_profile_does_not_override_adaptive_decisions():
    """Verify LearnerProfile is purely state-bearing and exposes no adaptive decision methods."""
    profile = LearnerProfile(
        learner_id="usr_01",
        preferred_difficulty=DifficultyLevel.BEGINNER,
    )
    # Profile does NOT implement adaptive actions or session step advancement
    assert not hasattr(profile, "decide_next_action")
    assert not hasattr(profile, "increase_difficulty")
    assert not hasattr(profile, "remediate_misconception")


def test_34_nonexistent_learner_raises_error(profile_service):
    """Verify querying or modifying non-existent learner raises LearnerNotFoundError."""
    with pytest.raises(LearnerNotFoundError):
        profile_service.get_profile("non_existent_usr")

    with pytest.raises(LearnerNotFoundError):
        profile_service.update_preferences("non_existent_usr", learning_goal="Goal")
