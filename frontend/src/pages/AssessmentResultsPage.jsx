import React from 'react';
import { useClassroom } from '../context/ClassroomContext';

/**
 * AssessmentResultsPage Component
 * Authoritative diagnostic learning report display for Member 2.
 * Strictly consumes Member 1's AssessmentReport schema without frontend grading or score recomputation.
 */
export default function AssessmentResultsPage({ onNavigate }) {
  const { assessmentReport, resetClassroom } = useClassroom();

  if (!assessmentReport) {
    return (
      <div className="results-empty-container">
        <div className="results-empty-card">
          <span className="empty-icon" aria-hidden="true">📊</span>
          <h2>No Assessment Results to Display</h2>
          <p>
            Complete a classroom teaching session and submit the final assessment to view your diagnostic learning report.
          </p>
          <div className="empty-actions-row">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigate && onNavigate('setup')}
            >
              Go to Setup Wizard
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onNavigate && onNavigate('final-assessment')}
            >
              Take Final Assessment
            </button>
          </div>
        </div>
      </div>
    );
  }

  const {
    letter_grade,
    overall_score,
    overall_mastery_level,
    total_questions,
    correct_answers,
    summary,
    concept_breakdowns = [],
    strengths = [],
    weaknesses = [],
    recommendations = [],
    misconceptions_detected = [],
    generated_at,
  } = assessmentReport;

  // Grade badge color helper
  const getGradeClass = (grade) => {
    switch (grade) {
      case 'A+':
      case 'A':
        return 'grade-excellent';
      case 'B':
        return 'grade-good';
      case 'C':
        return 'grade-satisfactory';
      case 'D':
      case 'F':
      default:
        return 'grade-needs-work';
    }
  };

  const handleStartNewLesson = () => {
    resetClassroom();
    if (typeof onNavigate === 'function') {
      onNavigate('setup');
    }
  };

  return (
    <div className="assessment-results-container">
      {/* 1. Header Banner */}
      <header className="results-header">
        <div className="results-title-group">
          <span className="results-icon" aria-hidden="true">🎉</span>
          <div>
            <h1 className="results-title">Great work! Here's Your Learning Report</h1>
            <p className="results-subtitle">
              Personalized breakdown of what you've mastered and recommendations for revision
            </p>
          </div>
        </div>

        {generated_at && (
          <span className="results-timestamp">
            Completed at {new Date(generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </header>

      {/* 2. Executive Overview Hero Card */}
      <section className="results-hero-card" aria-label="Learning Summary">
        <div className="hero-grade-column">
          <div className={`grade-circle ${getGradeClass(letter_grade)}`}>
            <span className="grade-letter">{letter_grade || 'A'}</span>
            <span className="grade-label">Grade</span>
          </div>
        </div>

        <div className="hero-stats-column">
          <div className="hero-metric">
            <span className="metric-num">
              {Math.round((overall_score || 0) * 100)}%
            </span>
            <span className="metric-label">Overall Score</span>
          </div>

          <div className="hero-metric">
            <span className="metric-num capitalize">
              {(overall_mastery_level || 'Proficient').replace('_', ' ')}
            </span>
            <span className="metric-label">Understanding</span>
          </div>

          <div className="hero-metric">
            <span className="metric-num">
              {correct_answers} / {total_questions}
            </span>
            <span className="metric-label">Questions Correct</span>
          </div>
        </div>
      </section>

      {/* 3. Teacher Narrative Summary */}
      {summary && (
        <section className="results-section-card narrative-card" aria-label="Teacher Note">
          <div className="section-header">
            <span className="section-icon">👩‍🏫</span>
            <h2 className="section-title">Teacher's Note</h2>
          </div>
          <p className="summary-narrative-text">{summary}</p>
        </section>
      )}

      {/* 4. Observed Strengths & Areas to Review Dual Row */}
      {(strengths.length > 0 || weaknesses.length > 0) && (
        <div className="results-dual-grid">
          {/* Conceptual Strengths */}
          {strengths.length > 0 && (
            <section className="results-section-card strengths-card" aria-label="Strong Areas">
              <div className="section-header">
                <span className="section-icon">🌟</span>
                <h2 className="section-title">STRONG AREAS</h2>
              </div>
              <ul className="feedback-bullets-list strengths-list">
                {strengths.map((item, idx) => (
                  <li key={idx} className="feedback-bullet-item">
                    <span className="bullet-marker">✓</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Areas to Review */}
          {weaknesses.length > 0 && (
            <section className="results-section-card weaknesses-card" aria-label="Needs Practice">
              <div className="section-header">
                <span className="section-icon">🔍</span>
                <h2 className="section-title">NEEDS PRACTICE</h2>
              </div>
              <ul className="feedback-bullets-list weaknesses-list">
                {weaknesses.map((item, idx) => (
                  <li key={idx} className="feedback-bullet-item">
                    <span className="bullet-marker">→</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {/* 5. Recommended Next Steps */}
      {recommendations.length > 0 && (
        <section className="results-section-card recommendations-card" aria-label="Recommended Next Step">
          <div className="section-header">
            <span className="section-icon">💡</span>
            <h2 className="section-title">RECOMMENDED NEXT STEP</h2>
          </div>
          <ul className="recommendations-list">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="rec-item">
                <span className="rec-num">{idx + 1}</span>
                <span className="rec-text">{rec}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 6. Per-Concept Mastery Breakdown */}
      {concept_breakdowns.length > 0 && (
        <section className="results-section-card" aria-label="Concept Breakdown">
          <div className="section-header">
            <span className="section-icon">🎯</span>
            <h2 className="section-title">Topic-by-Topic Breakdown</h2>
          </div>

          <div className="concept-breakdown-grid">
            {concept_breakdowns.map((item, idx) => {
              const pct = Math.round((item.score || 0) * 100);
              const statusClass =
                item.status === 'mastered'
                  ? 'status-mastered'
                  : item.status === 'needs_review'
                  ? 'status-needs-review'
                  : 'status-in-progress';
              const friendlyStatus =
                item.status === 'mastered'
                  ? 'Mastered'
                  : item.status === 'needs_review'
                  ? 'Needs Review'
                  : 'Improving';

              return (
                <div key={idx} className="concept-report-card">
                  <div className="concept-card-top">
                    <strong className="concept-report-name">{item.concept_name}</strong>
                    <span className={`concept-status-badge ${statusClass}`}>
                      {friendlyStatus}
                    </span>
                  </div>

                  <div className="concept-score-row">
                    <div className="concept-progress-track">
                      <div
                        className={`concept-progress-bar ${statusClass}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="concept-pct-label">{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 7. Misconceptions to Clarify */}
      {misconceptions_detected.length > 0 && (
        <section className="results-section-card misconceptions-card" aria-label="Misconceptions to Clarify">
          <div className="section-header">
            <span className="section-icon">💡</span>
            <h2 className="section-title">Misunderstandings to Clarify</h2>
          </div>
          <div className="misconceptions-list">
            {misconceptions_detected.map((misc, idx) => (
              <div key={idx} className="misc-report-card">
                <div className="misc-report-top">
                  <strong className="misc-report-title">{misc.description}</strong>
                </div>
                {misc.recommended_focus && (
                  <div className="misc-report-remedial">
                    <strong>Suggested focus:</strong> {misc.recommended_focus}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 8. Bottom Action Bar */}
      <footer className="results-actions-bar">
        <button
          type="button"
          className="btn btn-secondary btn-lg"
          onClick={handleStartNewLesson}
        >
          Learn Next Topic →
        </button>
        <button
          type="button"
          className="btn btn-primary btn-lg btn-go-revision"
          onClick={() => onNavigate && onNavigate('revision')}
        >
          Start Revision →
        </button>
      </footer>
    </div>
  );
}
