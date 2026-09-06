"""
Service for long-term pedagogical memory tracking and spaced repetition scheduling.

Features:
1. SuperMemo SM-2 algorithm calibrated with Ebbinghaus memory retention decay curves.
2. Cross-session memory tracking of concept repetitions, intervals, and easiness factors.
3. Prioritized review queue generator flagging concepts at risk of forgetting.
4. Historical learning audit trail aggregating session logs, attempts, and learning events.
5. Direct integration with SQLite persistence via LearnerRepository.
"""

from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LearnerNotFoundError
from app.db.models import AssessmentAttempt, ConceptMasteryRecord, Learner, LearningEvent, SessionLog, utc_now
from app.db.repository import LearnerRepository
from app.db.session import get_db_session
from app.schemas.adaptive import (
    ConceptMastery,
    MasteryLevel,
    MemoryUpdateResult,
    ReviewItem,
    ReviewQueue,
)

logger = logging.getLogger(__name__)


class LearningMemoryService:
    """Domain service managing long-term learner memory, retention curves, and review scheduling."""

    def __init__(self):
        pass

    # --------------------------------------------------------------------
    # SM-2 & Retention Curve Mathematics
    # --------------------------------------------------------------------

    @staticmethod
    def map_score_to_quality(score: float) -> int:
        """Map normalized performance score [0.0, 1.0] to SM-2 quality grade q in [0, 5]."""
        clamped = max(0.0, min(1.0, float(score)))
        if clamped >= 0.90:
            return 5  # Perfect recall without hesitation
        elif clamped >= 0.75:
            return 4  # Correct response after hesitation
        elif clamped >= 0.60:
            return 3  # Correct response with serious difficulty
        elif clamped >= 0.40:
            return 2  # Incorrect response; correct one remembered
        elif clamped >= 0.20:
            return 1  # Incorrect response; familiar concept
        return 0  # Complete blackout / total misconception

    @staticmethod
    def calculate_sm2_update(
        score: float,
        current_repetition: int,
        current_interval_days: float,
        current_easiness_factor: float,
    ) -> Tuple[int, float, float]:
        """Calculate updated SM-2 parameters: (new_rep, new_interval_days, new_ef)."""
        q = LearningMemoryService.map_score_to_quality(score)

        # Easiness Factor formula: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        new_ef = max(1.3, round(current_easiness_factor + ef_delta, 3))

        if q < 3:
            # Failed recall: reset repetition count and schedule immediate 1-day review
            new_rep = 0
            new_interval = 1.0
        else:
            # Successful recall: advance repetition counter and scale interval
            if current_repetition == 0:
                new_interval = 1.0
            elif current_repetition == 1:
                new_interval = 6.0
            else:
                new_interval = round(current_interval_days * new_ef, 1)
            new_rep = current_repetition + 1

        return new_rep, new_interval, new_ef

    @staticmethod
    def calculate_retention_probability(
        interval_days: float,
        elapsed_days: float,
    ) -> float:
        """Calculate retention probability using exponential Ebbinghaus decay:
        R(t) = 0.90 ^ (elapsed_days / max(0.5, interval_days))
        Calibrated such that at elapsed_days == interval_days, retention is exactly 90%.
        """
        if elapsed_days <= 0.0:
            return 1.0
        eff_interval = max(0.5, float(interval_days))
        decay_ratio = float(elapsed_days) / eff_interval
        # 0.90 ** decay_ratio
        retention = math.pow(0.90, decay_ratio)
        return round(max(0.0, min(1.0, retention)), 4)

    # --------------------------------------------------------------------
    # Memory State Updates
    # --------------------------------------------------------------------

    async def update_concept_memory(
        self,
        learner_id: str,
        concept_id: str,
        score: float,
        db_session: Optional[AsyncSession] = None,
    ) -> MemoryUpdateResult:
        """Update a learner's spaced repetition memory record following a learning interaction."""
        async def _do_update(s: AsyncSession) -> MemoryUpdateResult:
            repo = LearnerRepository(s)
            learner = await repo.get_learner(learner_id)
            if not learner:
                raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

            # Find existing record
            stmt = select(ConceptMasteryRecord).where(
                ConceptMasteryRecord.learner_id == learner_id,
                ConceptMasteryRecord.concept_id == concept_id,
            )
            res = await s.execute(stmt)
            existing = res.scalar_one_or_none()

            old_rep = existing.repetition_number if existing else 0
            old_interval = existing.interval_days if existing else 1.0
            old_ef = existing.easiness_factor if existing else 2.5

            new_rep, new_interval, new_ef = self.calculate_sm2_update(
                score=score,
                current_repetition=old_rep,
                current_interval_days=old_interval,
                current_easiness_factor=old_ef,
            )

            now = utc_now()
            next_due = now + timedelta(days=new_interval)

            mastery_level_val = (
                MasteryLevel.MASTERED if score >= 0.85 else (
                    MasteryLevel.PROFICIENT if score >= 0.70 else (
                        MasteryLevel.DEVELOPING if score >= 0.50 else MasteryLevel.EMERGING
                    )
                )
            )

            c_mastery = ConceptMastery(
                concept_id=concept_id,
                mastery_score=score,
                mastery_level=mastery_level_val,
                confidence=0.9,
                attempts=(existing.attempts + 1) if existing else 1,
                correct_attempts=((existing.correct_attempts if existing else 0) + (1 if score >= 0.75 else 0)),
                partial_attempts=((existing.partial_attempts if existing else 0) + (1 if 0.25 <= score < 0.75 else 0)),
                incorrect_attempts=((existing.incorrect_attempts if existing else 0) + (1 if score < 0.25 else 0)),
                last_score=score,
                repetition_number=new_rep,
                interval_days=new_interval,
                easiness_factor=new_ef,
                last_reviewed_at=now.isoformat(),
                next_review_due_at=next_due.isoformat(),
                retention_probability=1.0,
            )

            await repo.upsert_concept_mastery(learner_id, c_mastery)

            await repo.log_learning_event(
                learner_id=learner_id,
                concept_id=concept_id,
                event_type="MEMORY_UPDATED",
                payload={
                    "score": score,
                    "repetition_number": new_rep,
                    "interval_days": new_interval,
                    "easiness_factor": new_ef,
                    "next_review_due_at": next_due.isoformat(),
                },
            )

            return MemoryUpdateResult(
                concept_id=concept_id,
                old_interval_days=old_interval,
                new_interval_days=new_interval,
                old_easiness_factor=old_ef,
                new_easiness_factor=new_ef,
                repetition_number=new_rep,
                next_review_due_at=next_due.isoformat(),
                retention_probability=1.0,
            )

        if db_session is not None:
            return await _do_update(db_session)
        else:
            async with get_db_session() as s:
                return await _do_update(s)

    # --------------------------------------------------------------------
    # Review Queue & Memory Decay Retrieval
    # --------------------------------------------------------------------

    async def get_review_queue(
        self,
        learner_id: str,
        db_session: Optional[AsyncSession] = None,
        max_items: int = 10,
        retention_threshold: float = 0.85,
    ) -> ReviewQueue:
        """Generate a prioritized spaced repetition review queue based on memory decay curves."""
        async def _do_queue(s: AsyncSession) -> ReviewQueue:
            repo = LearnerRepository(s)
            learner = await repo.get_learner(learner_id)
            if not learner:
                raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

            stmt = select(ConceptMasteryRecord).where(
                ConceptMasteryRecord.learner_id == learner_id
            )
            res = await s.execute(stmt)
            records = res.scalars().all()

            now = utc_now()
            items: List[ReviewItem] = []

            for rec in records:
                # Calculate elapsed time in days
                if rec.last_reviewed_at:
                    rev_dt = rec.last_reviewed_at
                    if rev_dt.tzinfo is None:
                        rev_dt = rev_dt.replace(tzinfo=timezone.utc)
                    elapsed = max(0.0, (now - rev_dt).total_seconds() / 86400.0)
                else:
                    elapsed = max(0.0, (now - rec.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400.0) if rec.created_at else 1.0

                interval = max(0.5, rec.interval_days or 1.0)
                retention = self.calculate_retention_probability(interval_days=interval, elapsed_days=elapsed)

                # Overdue check: is now past next_review_due_at?
                is_overdue = False
                if rec.next_review_due_at:
                    due_dt = rec.next_review_due_at
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone.utc)
                    is_overdue = now >= due_dt

                # Priority/Urgency scoring: higher means more urgent to review
                # Formula: (1.0 - retention) * penalty for low mastery
                mastery_weight = 1.5 if rec.mastery_score < 0.70 else 1.0
                overdue_bonus = 0.5 if is_overdue else 0.0
                urgency = round((1.0 - retention) * mastery_weight + overdue_bonus, 4)

                if is_overdue or retention < 0.75:
                    action = "review_now"
                elif retention < retention_threshold:
                    action = "practice_soon"
                else:
                    action = "mastered_stable"

                c_name = rec.concept_id.replace("cpt_", "").replace("_", " ").title()
                try:
                    m_level = MasteryLevel(rec.mastery_level)
                except Exception:
                    m_level = MasteryLevel.EMERGING

                items.append(
                    ReviewItem(
                        concept_id=rec.concept_id,
                        concept_name=c_name,
                        mastery_score=rec.mastery_score,
                        mastery_level=m_level,
                        retention_probability=retention,
                        interval_days=rec.interval_days,
                        repetition_number=rec.repetition_number,
                        days_since_last_review=round(elapsed, 2),
                        urgency_score=urgency,
                        recommended_action=action,
                    )
                )

            # Sort descending by urgency score
            items.sort(key=lambda x: x.urgency_score, reverse=True)
            due_items = [it for it in items if it.recommended_action in ("review_now", "practice_soon")]

            return ReviewQueue(
                learner_id=learner_id,
                total_due=len(due_items),
                items=items[:max_items],
                generated_at=now.isoformat(),
            )

        if db_session is not None:
            return await _do_queue(db_session)
        else:
            async with get_db_session() as s:
                return await _do_queue(s)

    # --------------------------------------------------------------------
    # Cross-Session Historical Learning Analytics
    # --------------------------------------------------------------------

    async def get_historical_learning_summary(
        self,
        learner_id: str,
        db_session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Aggregate longitudinal learning analytics across all sessions, attempts, and memory records."""
        async def _do_summary(s: AsyncSession) -> Dict[str, Any]:
            repo = LearnerRepository(s)
            learner = await repo.get_learner(learner_id)
            if not learner:
                raise LearnerNotFoundError(f"Learner '{learner_id}' not found.")

            # Load concept masteries
            stmt_cm = select(ConceptMasteryRecord).where(ConceptMasteryRecord.learner_id == learner_id)
            records = (await s.execute(stmt_cm)).scalars().all()

            # Load session count
            stmt_sess = select(SessionLog).where(SessionLog.learner_id == learner_id)
            sessions = (await s.execute(stmt_sess)).scalars().all()

            # Load recent learning events
            stmt_ev = (
                select(LearningEvent)
                .where(LearningEvent.learner_id == learner_id)
                .order_by(desc(LearningEvent.created_at))
                .limit(10)
            )
            events = (await s.execute(stmt_ev)).scalars().all()

            # Load total attempts
            stmt_att = select(AssessmentAttempt).where(AssessmentAttempt.learner_id == learner_id)
            attempts = (await s.execute(stmt_att)).scalars().all()

            now = utc_now()
            retentions = []
            mastered_count = 0
            for r in records:
                if r.mastery_score >= 0.85:
                    mastered_count += 1
                if r.last_reviewed_at:
                    rev_dt = r.last_reviewed_at if r.last_reviewed_at.tzinfo else r.last_reviewed_at.replace(tzinfo=timezone.utc)
                    elapsed = max(0.0, (now - rev_dt).total_seconds() / 86400.0)
                else:
                    elapsed = 1.0
                retentions.append(self.calculate_retention_probability(r.interval_days, elapsed))

            avg_retention = round(sum(retentions) / len(retentions), 4) if retentions else 1.0

            return {
                "learner_id": learner_id,
                "name": learner.name,
                "overall_mastery": learner.overall_mastery,
                "average_score": learner.average_score,
                "total_assessments_taken": learner.assessment_count,
                "total_sessions": len(sessions),
                "total_questions_attempted": len(attempts),
                "total_concepts_tracked": len(records),
                "mastered_concepts_count": mastered_count,
                "average_retention_probability": avg_retention,
                "recent_events": [
                    {
                        "event_type": ev.event_type,
                        "concept_id": ev.concept_id,
                        "created_at": ev.created_at.isoformat() if ev.created_at else None,
                        "payload": ev.event_payload,
                    }
                    for ev in events
                ],
            }

        if db_session is not None:
            return await _do_summary(db_session)
        else:
            async with get_db_session() as s:
                return await _do_summary(s)


learning_memory_service = LearningMemoryService()
