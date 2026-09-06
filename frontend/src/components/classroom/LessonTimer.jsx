import React from 'react';

/**
 * LessonTimer Component
 * Renders the authoritative remaining time budget from Member 1 backend's time-adaptive engine.
 */
export default function LessonTimer({ remainingTimeMinutes = 20, status = 'idle' }) {
  const isUrgent = remainingTimeMinutes <= 5 && remainingTimeMinutes > 0;
  const isExpired = remainingTimeMinutes <= 0 && status === 'active';

  return (
    <div
      className={`lesson-timer-pill ${isUrgent ? 'timer-urgent' : ''} ${isExpired ? 'timer-expired' : ''}`}
      aria-label="Remaining Lesson Time"
      title="Lesson time remaining"
    >
      <span className="timer-icon">{isUrgent ? '⏳' : '⏱️'}</span>
      <div className="timer-content" style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
        <span className="timer-value">{remainingTimeMinutes}m</span>
        <span className="timer-label">remaining</span>
      </div>
    </div>
  );
}
