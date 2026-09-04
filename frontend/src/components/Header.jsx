import React from 'react';
import { useTestSession } from '../context/TestSessionContext';

export default function Header() {
  const { session, clearTestSession } = useTestSession();

  return (
    <div className="session-bar">
      <div className="session-info-group">
        <div className="session-item">
          <span className="session-label">Material:</span>
          <span
            className={`session-value ${!session.materialFilename ? 'empty' : ''}`}
            title={session.materialFilename || 'None'}
          >
            {session.materialFilename || 'None'}
          </span>
        </div>

        <div className="session-item">
          <span className="session-label">Material ID:</span>
          <span
            className={`session-value ${!session.materialId ? 'empty' : ''}`}
            title={session.materialId || 'None'}
          >
            {session.materialId || 'None'}
          </span>
        </div>

        <div className="session-item">
          <span className="session-label">Learner:</span>
          <span className="session-value" title={session.learnerId}>
            {session.learnerId}
          </span>
        </div>

        <div className="session-item">
          <span className="session-label">Concept:</span>
          <span
            className={`session-value ${!session.selectedConcept?.concept_id ? 'empty' : ''}`}
            title={session.selectedConcept?.name || session.selectedConcept?.concept_id || 'None'}
          >
            {session.selectedConcept?.name || session.selectedConcept?.concept_id || 'None'}
          </span>
        </div>

        <div className="session-item">
          <span className="session-label">Lesson:</span>
          <span
            className={`session-value ${!session.selectedLesson?.lesson_id ? 'empty' : ''}`}
            title={session.selectedLesson?.title || session.selectedLesson?.lesson_id || 'None'}
          >
            {session.selectedLesson?.title || session.selectedLesson?.lesson_id || 'None'}
          </span>
        </div>

        <div className="session-item">
          <span className="session-label">Question:</span>
          <span
            className={`session-value ${!session.selectedQuestion?.question_id ? 'empty' : ''}`}
            title={session.selectedQuestion?.question_id || 'None'}
          >
            {session.selectedQuestion?.question_id || 'None'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={clearTestSession}
          title="Clear all local test session variables"
        >
          🧹 Clear Test Session
        </button>
      </div>
    </div>
  );
}
