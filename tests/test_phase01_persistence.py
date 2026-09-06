import os
import tempfile
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidLearnerProfileError, LearnerNotFoundError
from app.db.models import (
    AssessmentAttempt,
    ConceptMasteryRecord,
    Learner,
    LearnerPreference,
    LearningEvent,
    SessionLog,
)
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.adaptive import ConceptMastery, MasteryLevel
from app.schemas.learner import SupportedLanguage
from app.schemas.lesson import DifficultyLevel
from app.services.learner_profile import LearnerProfileService


@pytest_asyncio.fixture
async def async_db_session():
    """Isolated in-memory SQLite database session for unit testing persistence models."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ====================================================================
# 1. Learner & Preference Creation
# ====================================================================

@pytest.mark.asyncio
async def test_01_learner_and_preference_creation(async_db_session):
    """Verify creating a learner creates both Learner and LearnerPreference records with correct defaults."""
    repo = LearnerRepository(async_db_session)
    learner = await repo.create_learner(
        learner_id="usr_test_01",
        name="Ada Lovelace",
        preferred_language="english",
        preferred_difficulty="intermediate",
        learning_goal="Understand Computing",
        teaching_style="socratic",
        available_time_minutes=30,
        desired_depth="deep_dive",
        total_lessons=5,
    )

    assert learner.id == "usr_test_01"
    assert learner.name == "Ada Lovelace"
    assert learner.total_lessons == 5
    assert learner.completed_lessons == []
    assert learner.assessment_count == 0
    assert learner.average_score == 0.0
    assert learner.overall_mastery == 0.0

    assert learner.preference is not None
    assert learner.preference.preferred_language == "english"
    assert learner.preference.preferred_difficulty == "intermediate"
    assert learner.preference.learning_goal == "Understand Computing"
    assert learner.preference.teaching_style == "socratic"
    assert learner.preference.available_time_minutes == 30
    assert learner.preference.desired_depth == "deep_dive"


@pytest.mark.asyncio
async def test_02_reject_empty_and_idempotent_recreation(async_db_session):
    """Verify validation rejects empty learner IDs and allows idempotent profile recreation."""
    repo = LearnerRepository(async_db_session)
    with pytest.raises(InvalidLearnerProfileError):
        await repo.create_learner(learner_id="")

    # Initial create
    l1 = await repo.create_learner(learner_id="usr_idem_01", name="Original")
    assert l1.name == "Original"

    # Re-create resets/updates cleanly
    l2 = await repo.create_learner(learner_id="usr_idem_01", name="Recreated")
    assert l2.id == "usr_idem_01"
    assert l2.name == "Recreated"



# ====================================================================
# 2. Preference Updates
# ====================================================================

@pytest.mark.asyncio
async def test_03_update_preferences(async_db_session):
    """Verify updating preferences persists language, difficulty, style, and time changes."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_test_pref")

    updated_pref = await repo.update_preferences(
        learner_id="usr_test_pref",
        preferred_language="hinglish",
        preferred_difficulty="advanced",
        learning_goal="Master Neural Networks",
        teaching_style="visual",
        available_time_minutes=45,
        desired_depth="deep_dive",
    )

    assert updated_pref.preferred_language == "hinglish"
    assert updated_pref.preferred_difficulty == "advanced"
    assert updated_pref.learning_goal == "Master Neural Networks"
    assert updated_pref.teaching_style == "visual"
    assert updated_pref.available_time_minutes == 45
    assert updated_pref.desired_depth == "deep_dive"


# ====================================================================
# 3. Concept Mastery Upsert & Overall Mastery Recalculation
# ====================================================================

@pytest.mark.asyncio
async def test_04_concept_mastery_upsert_and_recalculation(async_db_session):
    """Verify upserting masteries dynamically recalculates overall mastery and updates records."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_mastery_test")

    # 1. First concept mastery
    c1 = ConceptMastery(
        concept_id="cpt_photosynthesis_01",
        mastery_score=0.80,
        mastery_level=MasteryLevel.PROFICIENT,
        confidence=0.9,
        attempts=2,
        correct_attempts=2,
    )
    await repo.upsert_concept_mastery("usr_mastery_test", c1)
    learner = await repo.get_learner("usr_mastery_test")
    assert learner.overall_mastery == 0.80

    # 2. Second concept mastery
    c2 = ConceptMastery(
        concept_id="cpt_cellular_respiration_02",
        mastery_score=0.60,
        mastery_level=MasteryLevel.DEVELOPING,
        confidence=0.8,
        attempts=1,
        correct_attempts=0,
        partial_attempts=1,
    )
    await repo.upsert_concept_mastery("usr_mastery_test", c2)
    learner = await repo.get_learner("usr_mastery_test")
    assert learner.overall_mastery == 0.70  # (0.80 + 0.60) / 2

    # 3. Update existing concept mastery
    c1_updated = ConceptMastery(
        concept_id="cpt_photosynthesis_01",
        mastery_score=1.00,
        mastery_level=MasteryLevel.MASTERED,
        confidence=1.0,
        attempts=3,
        correct_attempts=3,
    )
    await repo.upsert_concept_mastery("usr_mastery_test", c1_updated)
    learner = await repo.get_learner("usr_mastery_test")
    assert learner.overall_mastery == 0.80  # (1.00 + 0.60) / 2
    assert len(learner.concept_masteries) == 2


# ====================================================================
# 4. Lesson Progress & Assessment Running Averages
# ====================================================================

@pytest.mark.asyncio
async def test_05_lesson_completion_deduplication(async_db_session):
    """Verify lesson IDs are deduplicated when recorded."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_progress_test")

    await repo.record_lesson_completion("usr_progress_test", "lsn_intro")
    await repo.record_lesson_completion("usr_progress_test", "lsn_advance")
    # Duplicate
    await repo.record_lesson_completion("usr_progress_test", "lsn_intro")

    learner = await repo.get_learner("usr_progress_test")
    assert learner.completed_lessons == ["lsn_intro", "lsn_advance"]


@pytest.mark.asyncio
async def test_06_assessment_score_running_average(async_db_session):
    """Verify incremental running average across assessments."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_score_test")

    # 1st score: 0.80
    await repo.record_assessment_score("usr_score_test", 0.80)
    l1 = await repo.get_learner("usr_score_test")
    assert l1.assessment_count == 1
    assert l1.average_score == 0.80

    # 2nd score: 0.60 -> average = 0.70
    await repo.record_assessment_score("usr_score_test", 0.60)
    l2 = await repo.get_learner("usr_score_test")
    assert l2.assessment_count == 2
    assert l2.average_score == 0.70


# ====================================================================
# 5. Learning Event Timeline & Session Logs
# ====================================================================

@pytest.mark.asyncio
async def test_07_learning_event_logging(async_db_session):
    """Verify recording and querying pedagogical learning events."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_events_test")

    # Log sequence of events
    await repo.log_learning_event(
        learner_id="usr_events_test",
        event_type="session_started",
        payload={"topic": "Quantum Mechanics"},
    )
    await repo.log_learning_event(
        learner_id="usr_events_test",
        event_type="concept_started",
        concept_id="cpt_wave_particle",
        payload={"difficulty": "beginner"},
    )
    await repo.log_learning_event(
        learner_id="usr_events_test",
        event_type="misconception_detected",
        concept_id="cpt_wave_particle",
        payload={"severity": "medium", "description": "Confuses wave with physical matter"},
    )

    events = await repo.get_learning_events("usr_events_test")
    assert len(events) == 3
    # Ordered newest first
    assert events[0].event_type == "misconception_detected"
    assert events[1].event_type == "concept_started"
    assert events[2].event_type == "session_started"


@pytest.mark.asyncio
async def test_08_session_log_lifecycle(async_db_session):
    """Verify session log creation, live step increment, and completion."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_session_test")

    sess = await repo.create_session_log(
        session_id="sess_live_101",
        learner_id="usr_session_test",
        topic="Biochemistry",
        difficulty="beginner",
        language="hinglish",
        available_time_minutes=20,
    )
    assert sess.id == "sess_live_101"
    assert sess.status == "active"
    assert sess.step_count == 0

    # Step increment and concept transition
    updated = await repo.update_session_log(
        session_id="sess_live_101",
        current_concept_id="cpt_enzymes",
        remaining_time_minutes=15,
        step_increment=1,
    )
    assert updated.current_concept_id == "cpt_enzymes"
    assert updated.remaining_time_minutes == 15
    assert updated.step_count == 1

    # End session
    ended = await repo.update_session_log(
        session_id="sess_live_101",
        status="completed",
    )
    assert ended.status == "completed"
    assert ended.ended_at is not None


# ====================================================================
# 6. Assessment Attempt Storage
# ====================================================================

@pytest.mark.asyncio
async def test_09_assessment_attempt_storage(async_db_session):
    """Verify persistent logging of individual assessment attempts."""
    repo = LearnerRepository(async_db_session)
    await repo.create_learner(learner_id="usr_attempt_test")

    attempt = await repo.record_assessment_attempt(
        evaluation_id="eval_001_hash",
        learner_id="usr_attempt_test",
        question_id="qst_dna_01",
        concept_id="cpt_dna_replication",
        question_type="conceptual",
        student_answer="DNA is copied in opposite directions",
        score=0.85,
        correctness=True,
        confidence=0.95,
        concepts_demonstrated=["Helicase unwind", "Leading strand"],
        concepts_missing=["Okazaki fragments"],
    )

    assert attempt.id == "eval_001_hash"
    assert attempt.score == 0.85
    assert attempt.correctness is True

    attempts = await repo.get_assessment_attempts("usr_attempt_test")
    assert len(attempts) == 1
    assert attempts[0].concepts_demonstrated == ["Helicase unwind", "Leading strand"]


# ====================================================================
# 7. Restart Persistence Verification (Survives Connection Teardown)
# ====================================================================

@pytest.mark.asyncio
async def test_10_restart_persistence_verification():
    """Verify that learner data written to a file-based SQLite database survives engine disposal and restart."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_persistence.db")
        db_url = f"sqlite+aiosqlite:///{db_file}"

        # 1. Initial run: Create learner, preferences, and mastery in Session 1
        engine_1 = create_async_engine(db_url, echo=False)
        async with engine_1.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory_1 = async_sessionmaker(engine_1, class_=AsyncSession, expire_on_commit=False)
        async with session_factory_1() as s1:
            repo1 = LearnerRepository(s1)
            await repo1.create_learner(
                learner_id="usr_persistent_bob",
                name="Bob",
                preferred_language="hindi",
                preferred_difficulty="advanced",
                learning_goal="Quantum Computing",
                available_time_minutes=60,
            )
            c_mastery = ConceptMastery(
                concept_id="cpt_qubits",
                mastery_score=0.95,
                mastery_level=MasteryLevel.MASTERED,
            )
            await repo1.upsert_concept_mastery("usr_persistent_bob", c_mastery)
            await s1.commit()

        # Completely tear down Session 1 and dispose engine
        await engine_1.dispose()

        # 2. Restart run: Open completely new Engine 2 pointing to the same file
        engine_2 = create_async_engine(db_url, echo=False)
        session_factory_2 = async_sessionmaker(engine_2, class_=AsyncSession, expire_on_commit=False)
        async with session_factory_2() as s2:
            repo2 = LearnerRepository(s2)
            restored_learner = await repo2.get_learner("usr_persistent_bob")

            assert restored_learner is not None
            assert restored_learner.id == "usr_persistent_bob"
            assert restored_learner.name == "Bob"
            assert restored_learner.overall_mastery == 0.95

            # Convert to Pydantic profile
            profile = repo2.to_learner_profile(restored_learner)
            assert profile.preferred_language == SupportedLanguage.HINDI
            assert profile.preferred_difficulty == DifficultyLevel.ADVANCED
            assert profile.learning_goal == "Quantum Computing"
            assert profile.mastered_concepts == ["cpt_qubits"]
            assert "cpt_qubits" in profile.concept_masteries

        await engine_2.dispose()


# ====================================================================
# 8. LearnerProfileService Database Async Integration
# ====================================================================

@pytest.mark.asyncio
async def test_11_learner_profile_service_db_methods(async_db_session):
    """Verify LearnerProfileService async DB methods persist and sync correctly."""
    svc = LearnerProfileService()

    # Create via DB
    profile = await svc.create_profile_db(
        session=async_db_session,
        learner_id="usr_svc_test",
        name="Charlie",
        preferred_language=SupportedLanguage.HINGLISH,
        preferred_difficulty=DifficultyLevel.BEGINNER,
        learning_goal="AI Teacher",
    )
    assert profile.learner_id == "usr_svc_test"
    assert profile.preferred_language == SupportedLanguage.HINGLISH

    # Update preferences via DB
    updated = await svc.update_preferences_db(
        session=async_db_session,
        learner_id="usr_svc_test",
        preferred_difficulty=DifficultyLevel.INTERMEDIATE,
    )
    assert updated.preferred_difficulty == DifficultyLevel.INTERMEDIATE

    # Retrieve from DB
    retrieved = await svc.get_profile_db(async_db_session, "usr_svc_test")
    assert retrieved.learner_id == "usr_svc_test"
    assert retrieved.preferred_difficulty == DifficultyLevel.INTERMEDIATE
