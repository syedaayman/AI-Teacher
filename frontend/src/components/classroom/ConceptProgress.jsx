import React from 'react';

/**
 * ConceptProgress Component
 * Visualizes learner progress across the concept sequence of the active teaching session.
 */
export default function ConceptProgress({
  currentConceptName,
  conceptIndex = 0,
  totalConcepts = 0,
}) {
  const safeTotal = Math.max(totalConcepts, 0);
  const currentStepNum = safeTotal > 0 ? Math.min(conceptIndex + 1, safeTotal) : 0;
  const percentage = safeTotal > 0 ? Math.round((currentStepNum / safeTotal) * 100) : 0;

  return (
    <div className="concept-progress-bar-container" aria-label="Curriculum Progress">
      <div className="progress-info-row">
        <div className="progress-concept-name" title={currentConceptName || 'Concept Progress'}>
          <span className="concept-icon">🎯</span>
          <span className="concept-label">
            {currentConceptName ? currentConceptName : safeTotal > 0 ? `Concept ${currentStepNum}` : 'Ready'}
          </span>
        </div>
        <div className="progress-counter">
          <span className="counter-fraction">
            {safeTotal > 0 ? `${currentStepNum} / ${safeTotal} Concepts` : 'No concepts loaded'}
          </span>
          <span className="counter-percent">({percentage}%)</span>
        </div>
      </div>

      <div className="progress-track" role="progressbar" aria-valuenow={percentage} aria-valuemin="0" aria-valuemax="100">
        <div
          className="progress-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
