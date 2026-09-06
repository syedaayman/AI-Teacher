"""
Unit and Integration Tests for Phase 7: Long-Term Learning Memory and Spaced Repetition.

Verifies:
1. SuperMemo SM-2 quality grade mapping and parameter evolution.
2. Ebbinghaus retention decay curve calculation.
3. Memory update persistence and event audit logging.
4. Spaced repetition review queue generation and urgency prioritization.
5. Longitudinal cross-session learning analytics and historical memory summary.
"""

from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import ConceptMasteryRecord, Learner, LearningEvent, SessionLog
from app.db.repository import LearnerRepository
from app.db.session import Base
from app.schemas.adaptive import MasteryLevel
from app.services.learning_memory_service import LearningMemoryService


@pytest_asyncio.fixture
async def async_db_session():
    """Isolated in-memory SQLite database session for memory and spaced repetition testing."""
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
        repo = LearnerRepository(session)
        await repo.create_learner(
            learner_id="memory_learner_01",
            name="Ada Lovelace",
            preferred_language="english",
            preferred_difficulty="intermediate",
        )
        yield session


# ============================================================================
# Test 1: SM-2 Grade Mapping
# ============================================================================

def test_sm2_quality_mapping():
    """Verify performance scores map to standard SM-2 0-5 quality grades."""
    service = LearningMemoryService()

    assert service.map_score_to_quality(1.0) == 5
    assert service.map_score_to_quality(0.95) == 5
    assert service.map_score_to_quality(0.80) == 4
    assert service.map_score_to_quality(0.65) == 3
    assert service.map_score_to_quality(0.45) == 2
    assert service.map_score_to_quality(0.25) == 1
    assert service.map_score_to_quality(0.10) == 0


# ============================================================================
# Test 2: SM-2 Parameter Progression & Failed Recall Reset
# ============================================================================

def test_sm2_algorithm_progression():
    """Verify interval growth on success and reset on failure."""
    service = LearningMemoryService()

    # Iteration 1: first successful review (q=5)
    rep1, int1, ef1 = service.calculate_sm2_update(
        score=1.0,
        current_repetition=0,
        current_interval_days=1.0,
        current_easiness_factor=2.5,
    )
    assert rep1 == 1
    assert int1 == 1.0
    assert ef1 == 2.6  # 2.5 + (0.1 - 0) = 2.6

    # Iteration 2: second successful review (q=4)
    rep2, int2, ef2 = service.calculate_sm2_update(
        score=0.80,
        current_repetition=rep1,
        current_interval_days=int1,
        current_easiness_factor=ef1,
    )
    assert rep2 == 2
    assert int2 == 6.0  # standard SM-2 second interval
    assert ef2 == 2.6  # ef delta for q=4 is 0.1 - (1 * 0.1) = 0.0

    # Iteration 3: third successful review (q=5)
    rep3, int3, ef3 = service.calculate_sm2_update(
        score=0.95,
        current_repetition=rep2,
        current_interval_days=int2,
        current_easiness_factor=ef2,
    )
    assert rep3 == 3
    assert int3 == round(6.0 * ef3, 1)  # 6.0 * 2.7 = 16.2
    assert ef3 == 2.7

    # Iteration 4: failed recall / misconception (score=0.20, q=1)
    rep_fail, int_fail, ef_fail = service.calculate_sm2_update(
        score=0.20,
        current_repetition=rep3,
        current_interval_days=int3,
        current_easiness_factor=ef3,
    )
    assert rep_fail == 0  # reset repetition
    assert int_fail == 1.0  # review tomorrow
    assert ef_fail < ef3
    assert ef_fail >= 1.3  # clamped to minimum


# ============================================================================
# Test 3: Ebbinghaus Retention Decay Curve
# ============================================================================

def test_ebbinghaus_retention_decay():
    """Verify memory decay satisfies retention targets over elapsed time."""
    service = LearningMemoryService()
    interval = 10.0

    # 0 days elapsed -> 100% retention
    r0 = service.calculate_retention_probability(interval_days=interval, elapsed_days=0.0)
    assert r0 == 1.0

    # Exactly interval days elapsed -> exactly 90% retention target
    r_target = service.calculate_retention_probability(interval_days=interval, elapsed_days=10.0)
    assert r_target == 0.90

    # 2x interval elapsed -> 0.90^2 = 0.81
    r_double = service.calculate_retention_probability(interval_days=interval, elapsed_days=20.0)
    assert r_double == 0.81

    # Far in the future -> memory decay below threshold
    r_far = service.calculate_retention_probability(interval_days=interval, elapsed_days=60.0)
    assert r_far < 0.60


# ============================================================================
# Test 4: Persistent Memory Updates
# ============================================================================

@pytest.mark.asyncio
async def test_update_concept_memory_persistence(async_db_session: AsyncSession):
    """Verify update_concept_memory persists SM-2 values and logs event."""
    service = LearningMemoryService()

    res = await service.update_concept_memory(
        learner_id="memory_learner_01",
        concept_id="cpt_dynamic_programming",
        score=0.92,
        db_session=async_db_session,
    )

    assert res.concept_id == "cpt_dynamic_programming"
    assert res.repetition_number == 1
    assert res.new_interval_days == 1.0
    assert res.new_easiness_factor == 2.6
    assert res.retention_probability == 1.0

    # Check DB record
    stmt = select(ConceptMasteryRecord).where(
        ConceptMasteryRecord.learner_id == "memory_learner_01",
        ConceptMasteryRecord.concept_id == "cpt_dynamic_programming",
    )
    rec = (await async_db_session.execute(stmt)).scalar_one_or_none()
    assert rec is not None
    assert rec.repetition_number == 1
    assert rec.interval_days == 1.0
    assert rec.easiness_factor == 2.6
    assert rec.next_review_due_at is not None

    # Check LearningEvent logged
    stmt_ev = select(LearningEvent).where(
        LearningEvent.learner_id == "memory_learner_01",
        LearningEvent.event_type == "MEMORY_UPDATED",
    )
    ev = (await async_db_session.execute(stmt_ev)).scalar_one_or_none()
    assert ev is not None
    assert ev.event_payload["repetition_number"] == 1


# ============================================================================
# Test 5: Prioritized Spaced Repetition Review Queue
# ============================================================================

@pytest.mark.asyncio
async def test_review_queue_prioritization(async_db_session: AsyncSession):
    """Verify review queue flags overdue concepts and sorts by urgency score."""
    service = LearningMemoryService()
    now = datetime.now(timezone.utc)

    # Seed 3 concept records with different elapsed times and schedules
    # 1. Overdue concept (reviewed 10 days ago, 3-day interval)
    c1 = ConceptMasteryRecord(
        learner_id="memory_learner_01",
        concept_id="cpt_binary_search",
        mastery_score=0.50,
        mastery_level="developing",
        attempts=2,
        repetition_number=1,
        interval_days=3.0,
        easiness_factor=2.4,
        last_reviewed_at=now - timedelta(days=10),
        next_review_due_at=now - timedelta(days=7),
    )

    # 2. Freshly reviewed stable concept (reviewed today, 15-day interval)
    c2 = ConceptMasteryRecord(
        learner_id="memory_learner_01",
        concept_id="cpt_sorting",
        mastery_score=0.95,
        mastery_level="mastered",
        attempts=5,
        repetition_number=3,
        interval_days=15.0,
        easiness_factor=2.7,
        last_reviewed_at=now - timedelta(hours=2),
        next_review_due_at=now + timedelta(days=15),
    )

    # 3. Concept needing review soon (reviewed 5 days ago, 6-day interval)
    c3 = ConceptMasteryRecord(
        learner_id="memory_learner_01",
        concept_id="cpt_linked_lists",
        mastery_score=0.75,
        mastery_level="proficient",
        attempts=3,
        repetition_number=2,
        interval_days=6.0,
        easiness_factor=2.5,
        last_reviewed_at=now - timedelta(days=5),
        next_review_due_at=now + timedelta(days=1),
    )

    async_db_session.add_all([c1, c2, c3])
    await async_db_session.flush()

    queue = await service.get_review_queue(
        learner_id="memory_learner_01",
        db_session=async_db_session,
    )

    assert len(queue.items) == 3
    # Top urgency should be the overdue binary search
    assert queue.items[0].concept_id == "cpt_binary_search"
    assert queue.items[0].recommended_action == "review_now"
    assert queue.items[0].urgency_score > queue.items[1].urgency_score

    # Freshly mastered concept should be lowest urgency
    assert queue.items[-1].concept_id == "cpt_sorting"
    assert queue.items[-1].recommended_action == "mastered_stable"


# ============================================================================
# Test 6: Historical Cross-Session Learning Analytics
# ============================================================================

@pytest.mark.asyncio
async def test_historical_learning_summary(async_db_session: AsyncSession):
    """Verify longitudinal summary compiles metrics across sessions and attempts."""
    service = LearningMemoryService()
    now = datetime.now(timezone.utc)

    # Add a session log
    sess = SessionLog(
        id="ses_history_01",
        learner_id="memory_learner_01",
        topic="Data Structures",
        status="completed",
        started_at=now - timedelta(hours=3),
        ended_at=now - timedelta(hours=2),
    )
    # Add an event
    ev = LearningEvent(
        learner_id="memory_learner_01",
        session_id="ses_history_01",
        concept_id="cpt_trees",
        event_type="LESSON_COMPLETED",
        event_payload={"score": 0.90},
        created_at=now - timedelta(hours=2),
    )
    async_db_session.add_all([sess, ev])
    await async_db_session.flush()

    summary = await service.get_historical_learning_summary(
        learner_id="memory_learner_01",
        db_session=async_db_session,
    )

    assert summary["learner_id"] == "memory_learner_01"
    assert summary["name"] == "Ada Lovelace"
    assert summary["total_sessions"] >= 1
    assert len(summary["recent_events"]) >= 1
    assert summary["recent_events"][0]["event_type"] == "LESSON_COMPLETED"
