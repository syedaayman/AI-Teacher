from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class Learner(Base):
    """Canonical persistent Learner entity."""
    __tablename__ = "learners"

    id = Column(String(64), primary_key=True, index=True)  # learner_id
    name = Column(String(128), nullable=True)
    total_lessons = Column(Integer, default=0, nullable=False)
    completed_lessons = Column(JSON, default=list, nullable=False)
    assessment_count = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, default=0.0, nullable=False)
    overall_mastery = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    preference = relationship(
        "LearnerPreference",
        back_populates="learner",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    concept_masteries = relationship(
        "ConceptMasteryRecord",
        back_populates="learner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    session_logs = relationship(
        "SessionLog",
        back_populates="learner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    learning_events = relationship(
        "LearningEvent",
        back_populates="learner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    assessment_attempts = relationship(
        "AssessmentAttempt",
        back_populates="learner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LearnerPreference(Base):
    """Instructional preferences and curriculum goals for a learner."""
    __tablename__ = "learner_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(64), ForeignKey("learners.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    preferred_language = Column(String(32), default="english", nullable=False)
    preferred_difficulty = Column(String(32), default="intermediate", nullable=False)
    learning_goal = Column(Text, nullable=True)
    teaching_style = Column(String(32), default="interactive", nullable=False)
    available_time_minutes = Column(Integer, default=20, nullable=False)
    desired_depth = Column(String(32), default="standard", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    learner = relationship("Learner", back_populates="preference")


class ConceptMasteryRecord(Base):
    """Persistent tracking of concept proficiency, confidence, and attempt history."""
    __tablename__ = "concept_mastery_records"
    __table_args__ = (
        UniqueConstraint("learner_id", "concept_id", name="uq_learner_concept"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(64), ForeignKey("learners.id", ondelete="CASCADE"), index=True, nullable=False)
    concept_id = Column(String(64), index=True, nullable=False)
    mastery_score = Column(Float, default=0.0, nullable=False)
    mastery_level = Column(String(32), default="not_started", nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    correct_attempts = Column(Integer, default=0, nullable=False)
    partial_attempts = Column(Integer, default=0, nullable=False)
    incorrect_attempts = Column(Integer, default=0, nullable=False)
    last_score = Column(Float, nullable=True)
    repetition_number = Column(Integer, default=0, nullable=False)
    interval_days = Column(Float, default=1.0, nullable=False)
    easiness_factor = Column(Float, default=2.5, nullable=False)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    next_review_due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    learner = relationship("Learner", back_populates="concept_masteries")


class SessionLog(Base):
    """Historical and active learning session record."""
    __tablename__ = "session_logs"

    id = Column(String(64), primary_key=True, index=True)  # session_id
    learner_id = Column(String(64), ForeignKey("learners.id", ondelete="CASCADE"), index=True, nullable=False)
    lesson_id = Column(String(64), nullable=True, index=True)
    topic = Column(String(256), nullable=True)
    material_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="active", nullable=False)  # active, completed, abandoned, paused
    current_concept_id = Column(String(64), nullable=True)
    current_difficulty = Column(String(32), default="intermediate", nullable=False)
    language = Column(String(32), default="english", nullable=False)
    available_time_minutes = Column(Integer, default=20, nullable=False)
    remaining_time_minutes = Column(Integer, default=20, nullable=False)
    desired_depth = Column(String(32), default="standard", nullable=False)
    step_count = Column(Integer, default=0, nullable=False)
    session_metadata = Column(JSON, default=dict, nullable=False)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    learner = relationship("Learner", back_populates="session_logs")
    learning_events = relationship("LearningEvent", back_populates="session", cascade="all, delete-orphan")


class LearningEvent(Base):
    """Immutable audit and memory log of fine-grained pedagogical events."""
    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(64), ForeignKey("learners.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id = Column(String(64), ForeignKey("session_logs.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), index=True, nullable=False)
    event_payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)

    # Relationships
    learner = relationship("Learner", back_populates="learning_events")
    session = relationship("SessionLog", back_populates="learning_events")


class AssessmentAttempt(Base):
    """Persistent log of individual assessment question attempts."""
    __tablename__ = "assessment_attempts"

    id = Column(String(64), primary_key=True, index=True)  # evaluation_id
    learner_id = Column(String(64), ForeignKey("learners.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id = Column(String(64), nullable=True, index=True)
    question_id = Column(String(64), index=True, nullable=False)
    concept_id = Column(String(64), index=True, nullable=False)
    question_type = Column(String(32), nullable=False)
    student_answer = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    correctness = Column(Boolean, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    concepts_demonstrated = Column(JSON, default=list, nullable=False)
    concepts_missing = Column(JSON, default=list, nullable=False)
    misconception_diagnosed = Column(Text, nullable=True)
    severity = Column(String(32), nullable=True)
    evaluation_rubric = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    learner = relationship("Learner", back_populates="assessment_attempts")
