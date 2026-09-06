import React, { useState, useEffect } from 'react';
import { useClassroom } from '../../context/ClassroomContext';

/**
 * QuestionPanel Component
 * Student-facing interactive assessment UI that feels like an attentive human teacher:
 * - Heading: "Let's check your understanding."
 * - Supports: MCQ, Short Answer, Conceptual, Application, Problem Solving, Explain in Your Own Words
 * - No frontend grading: submits directly to backend for diagnostic evaluation
 * - Misconception Experience: Replaces generic "Incorrect" with "You're close, but there's one important idea to fix."
 * - Adaptive Decisions clearly mapped to human pedagogical phrases:
 *   - reteach_concept: "Let's look at that one more time."
 *   - retry_question: "Try another example."
 *   - decrease_difficulty: "Let's make this a little simpler."
 *   - increase_difficulty: "You're ready for a challenge."
 *   - advance_concept: "Great! Let's move on."
 *   - review_prerequisite: "Let's quickly revisit something important."
 */
/**
 * Map adaptive action into friendly human phrases
 */
export const getAdaptiveActionInfo = (action) => {
  switch (action) {
    case 'remediate_misconception':
      return {
        bannerText: "You're close, but there's one important idea to fix.",
        buttonLabel: "Let's fix this misconception together →",
        icon: '💡',
      };
    case 'reteach_concept':
      return {
        bannerText: "Let's look at that one more time.",
        buttonLabel: "Let's look at that one more time →",
        icon: '🔄',
      };
    case 'retry_question':
      return {
        bannerText: 'Try another example.',
        buttonLabel: 'Try another example →',
        icon: '✍️',
      };
    case 'decrease_difficulty':
      return {
        bannerText: "Let's make this a little simpler.",
        buttonLabel: "Let's make this a little simpler →",
        icon: '🌱',
      };
    case 'increase_difficulty':
      return {
        bannerText: "You're ready for a challenge.",
        buttonLabel: "You're ready for a challenge →",
        icon: '⚡',
      };
    case 'advance_concept':
      return {
        bannerText: "Great! Let's move on.",
        buttonLabel: "Next Concept →",
        icon: '🚀',
      };
    case 'review_prerequisite':
      return {
        bannerText: "Let's quickly revisit something important.",
        buttonLabel: "Review Concept →",
        icon: '📚',
      };
    default:
      return {
        bannerText: 'Continue learning with your teacher.',
        buttonLabel: 'Continue with Teacher →',
        icon: '➡️',
      };
  }
};

export default function QuestionPanel() {
  const {
    question,
    evaluation,
    misconceptionAnalysis,
    adaptation,
    delivery,
    submitting,
    loading,
    error,
    submitAnswer,
    clearEvaluation,
    setTeacherState,
  } = useClassroom();

  // Local transient answer states
  const [selectedOption, setSelectedOption] = useState('');
  const [textAnswer, setTextAnswer] = useState('');
  const [reasoning, setReasoning] = useState('');
  const [showReasoning, setShowReasoning] = useState(false);
  const [localError, setLocalError] = useState(null);
  const [remediationTab, setRemediationTab] = useState('explanation'); // 'explanation' | 'analogy' | 'misconception'

  // Reset answer states cleanly whenever a new question arrives
  useEffect(() => {
    if (question?.question_id) {
      setSelectedOption('');
      setTextAnswer('');
      setReasoning('');
      setShowReasoning(false);
      setLocalError(null);
      setRemediationTab('explanation');
      if (typeof setTeacherState === 'function') {
        setTeacherState('listening');
      }
    }
  }, [question?.question_id, setTeacherState]);

  // If no active question and no evaluation to review, do not render
  if (!question && !evaluation) {
    return null;
  }

  const hasEvaluated = Boolean(evaluation);
  const isMCQ = question?.question_type === 'mcq' || (question?.options && question.options.length > 0);

  // Normalize question type label into user-friendly wording
  const getQuestionTypeLabel = (type) => {
    switch (type) {
      case 'mcq':
        return 'Multiple Choice';
      case 'short_answer':
        return 'Short Answer';
      case 'conceptual':
        return 'Conceptual Analysis';
      case 'application':
        return 'Application & Problem Solving';
      case 'problem_solving':
        return 'Problem Solving';
      case 'explain_in_own_words':
      case 'explain':
        return 'Explain in Your Own Words';
      default:
        return 'Comprehension Check';
    }
  };

  const adaptiveInfo = adaptation ? getAdaptiveActionInfo(adaptation.action) : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError(null);

    // Validate presence of student answer
    if (isMCQ && !selectedOption) {
      setLocalError('Please select an option before submitting.');
      return;
    }

    if (!isMCQ && !textAnswer.trim()) {
      setLocalError('Please enter your response before submitting.');
      return;
    }

    try {
      if (typeof setTeacherState === 'function') {
        setTeacherState('thinking');
      }
      const evalResult = await submitAnswer({
        question_id: question?.question_id,
        selected_option: isMCQ ? selectedOption : null,
        answer_text: !isMCQ ? textAnswer.trim() : null,
        reasoning: reasoning.trim() || null,
      });

      // Synchronize teacher reaction based on evaluation
      if (typeof setTeacherState === 'function') {
        if (evalResult?.evaluation?.correctness || (evalResult?.evaluation?.score && evalResult.evaluation.score >= 0.7)) {
          setTeacherState('encouraging');
        } else {
          setTeacherState('thinking');
        }
      }
    } catch (err) {
      setLocalError('Something went wrong while checking your answer. Please try again.');
      if (typeof setTeacherState === 'function') {
        setTeacherState('listening');
      }
    }
  };

  const handleContinue = () => {
    if (typeof clearEvaluation === 'function') {
      clearEvaluation();
    }
    if (typeof setTeacherState === 'function') {
      setTeacherState('idle');
    }
  };

  // Check whether submission can proceed
  const canSubmit = !submitting && !loading && (isMCQ ? Boolean(selectedOption) : Boolean(textAnswer.trim()));

  const isCorrect = evaluation?.correctness === true || (evaluation?.score && evaluation.score >= 0.85);
  const isPartial = !isCorrect && evaluation?.score && evaluation.score >= 0.5;

  return (
    <section className="classroom-aux-panel question-panel-card" aria-label="Interactive Assessment">
      {/* 1. Header: Human-like Heading */}
      <div className="aux-header question-header">
        <div className="aux-title-group">
          <span className="aux-icon" aria-hidden="true">❓</span>
          <h3 className="aux-title">Let's check your understanding.</h3>
        </div>
        <div className="question-meta-badges">
          {question?.question_type && (
            <span className="badge badge-primary">
              {getQuestionTypeLabel(question.question_type)}
            </span>
          )}
          {question?.difficulty && (
            <span className="badge badge-secondary capitalize">
              {question.difficulty}
            </span>
          )}
        </div>
      </div>

      {/* 2. Error Notice Banner */}
      {(localError || error) && (
        <div className="question-error-alert" role="alert">
          <span className="alert-icon">⚠️</span>
          <span className="alert-text">{localError || error}</span>
          <button
            type="button"
            className="btn btn-xs btn-link"
            onClick={() => setLocalError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 3. Question Prompt */}
      {question?.question_text && (
        <div className="question-prompt-box">
          <p className="question-prompt-text">{question.question_text}</p>
          {question.learning_objective && (
            <span className="learning-objective-tag">
              🎯 Learning Goal: {question.learning_objective}
            </span>
          )}
        </div>
      )}

      {/* 4. Interactive Answer Input (Locked if already evaluated) */}
      {!hasEvaluated && question && (
        <form onSubmit={handleSubmit} className="question-answer-form">
          {isMCQ ? (
            /* MCQ Option Radio Group */
            <fieldset className="mcq-options-fieldset" disabled={submitting}>
              <legend className="sr-only">Multiple Choice Options</legend>
              <div className="mcq-options-list">
                {question.options.map((opt, i) => {
                  const letter = String.fromCharCode(65 + i);
                  const isChecked = selectedOption === opt;

                  return (
                    <label
                      key={i}
                      className={`mcq-option-label ${isChecked ? 'selected' : ''}`}
                    >
                      <input
                        type="radio"
                        name={`mcq_option_${question.question_id}`}
                        value={opt}
                        checked={isChecked}
                        onChange={() => setSelectedOption(opt)}
                        disabled={submitting}
                        className="mcq-radio-input"
                      />
                      <span className="opt-letter" aria-hidden="true">{letter}</span>
                      <span className="opt-text">{opt}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ) : (
            /* Free-Text / Open-Ended Working */
            <div className="free-text-input-group">
              <label htmlFor="student-free-text-answer" className="input-label">
                Your Answer or Working:
              </label>
              <textarea
                id="student-free-text-answer"
                className="form-control question-textarea"
                rows={4}
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                disabled={submitting}
                placeholder="Type your explanation, intuition, or worked steps here..."
                required
              />
            </div>
          )}

          {/* Optional Reasoning / Thought Model Input */}
          <div className="reasoning-toggle-container">
            <button
              type="button"
              className="btn-toggle-reasoning"
              onClick={() => setShowReasoning(!showReasoning)}
            >
              {showReasoning ? '▲ Hide Thinking' : '💡 + Share your thought process (Helps your teacher diagnose)'}
            </button>
            {showReasoning && (
              <div className="reasoning-input-box">
                <label htmlFor="student-reasoning-input" className="reasoning-label">
                  Explain your thought process:
                </label>
                <textarea
                  id="student-reasoning-input"
                  className="form-control reasoning-textarea"
                  rows={2}
                  value={reasoning}
                  onChange={(e) => setReasoning(e.target.value)}
                  disabled={submitting}
                  placeholder="e.g. I deduced this because the call stack unwinds in reverse order..."
                />
              </div>
            )}
          </div>

          {/* Submit Button */}
          <div className="question-submit-row">
            <button
              type="submit"
              className="btn btn-primary btn-submit-answer"
              disabled={!canSubmit}
            >
              {submitting ? (
                <>
                  <span className="spinner-sm" aria-hidden="true" />
                  Your Teacher is Reviewing...
                </>
              ) : (
                'Submit Answer →'
              )}
            </button>
          </div>
        </form>
      )}

      {/* 5. Diagnostic Evaluation & Human-like Remediation Area */}
      {hasEvaluated && (
        <div className="question-feedback-card" role="region" aria-live="polite">
          {/* Section 9: Supportive Evaluation Banner */}
          <div className="feedback-result-header">
            <div className="result-status-group">
              <span
                className={`evaluation-badge ${
                  isCorrect
                    ? 'eval-correct'
                    : isPartial
                    ? 'eval-partial'
                    : 'eval-incorrect'
                }`}
              >
                {isCorrect
                  ? '✓ Excellent! You understood the key principle.'
                  : isPartial
                  ? '⚡ Good attempt! You have the general idea, with one detail to refine.'
                  : "You're close, but there's one important idea to fix."}
              </span>
              <span className="score-badge">
                Mastery: {Math.round((evaluation.score || 0) * 100)}%
              </span>
            </div>
          </div>

          {/* Section 8: Visual Adaptive Teaching Banner */}
          {adaptiveInfo && (
            <div className="adaptive-pedagogy-banner">
              <span className="adaptive-icon">{adaptiveInfo.icon}</span>
              <div className="adaptive-content">
                <span className="adaptive-badge">Teacher's Adaptive Decision</span>
                <h4 className="adaptive-headline">{adaptiveInfo.bannerText}</h4>
                {adaptation.reason && (
                  <p className="adaptive-reason">{adaptation.reason}</p>
                )}
              </div>
            </div>
          )}

          {/* Student's Answer Review */}
          {evaluation.student_answer && (
            <div className="student-submitted-review">
              <span className="review-label">Your Response:</span>
              <p className="review-text">{evaluation.student_answer}</p>
            </div>
          )}

          {/* Teacher's Spoken Remediation Feedback */}
          {evaluation.feedback && (
            <div className="feedback-narrative-box">
              <div className="teacher-feedback-header">
                <span className="teacher-icon">👩‍🏫</span>
                <span className="feedback-label">Teacher's Explanation:</span>
              </div>
              <p className="feedback-text">{evaluation.feedback}</p>
            </div>
          )}

          {/* Remediation Tabs: Explain Differently / Analogy / Clarification */}
          <div className="remediation-tools-section">
            <div className="remediation-tabs-row">
              <button
                type="button"
                className={`remediation-tab-btn ${remediationTab === 'explanation' ? 'active' : ''}`}
                onClick={() => setRemediationTab('explanation')}
              >
                📖 Detailed Explanation
              </button>
              {(delivery?.analogy || evaluation.evidence) && (
                <button
                  type="button"
                  className={`remediation-tab-btn ${remediationTab === 'analogy' ? 'active' : ''}`}
                  onClick={() => setRemediationTab('analogy')}
                >
                  💡 Intuitive Analogy
                </button>
              )}
              {misconceptionAnalysis?.detected && misconceptionAnalysis.misconceptions?.length > 0 && (
                <button
                  type="button"
                  className={`remediation-tab-btn ${remediationTab === 'misconception' ? 'active' : ''}`}
                  onClick={() => setRemediationTab('misconception')}
                >
                  ⚠️ What to Clarify
                </button>
              )}
            </div>

            <div className="remediation-tab-content">
              {remediationTab === 'explanation' && (
                <div className="remediation-pane">
                  {evaluation.explanation && (
                    <p className="pane-text">
                      <strong>Key Principle:</strong> {evaluation.explanation}
                    </p>
                  )}
                  {evaluation.reasoning_assessment && (
                    <p className="pane-text">
                      <strong>Thought Process Analysis:</strong> {evaluation.reasoning_assessment}
                    </p>
                  )}
                  {evaluation.expected_answer && (
                    <div className="expected-answer-subbox">
                      <span className="subbox-label">Reference Solution:</span>
                      <p className="subbox-text">{evaluation.expected_answer}</p>
                    </div>
                  )}
                </div>
              )}

              {remediationTab === 'analogy' && (
                <div className="remediation-pane analogy-pane">
                  <span className="analogy-heading">💡 Think of it like this:</span>
                  <p className="analogy-body">
                    {delivery?.analogy ||
                      evaluation.evidence ||
                      "Break the problem down step by step: connect each action to its immediate result."}
                  </p>
                </div>
              )}

              {remediationTab === 'misconception' && misconceptionAnalysis?.misconceptions?.[0] && (
                <div className="remediation-pane misconception-pane">
                  <div className="misc-header">
                    <span className="misc-icon">⚠️</span>
                    <strong>Concept to Clarify:</strong>
                  </div>
                  <p className="misc-body">
                    {misconceptionAnalysis.misconceptions[0].description}
                  </p>
                  {misconceptionAnalysis.misconceptions[0].recommended_focus && (
                    <p className="misc-focus">
                      <strong>Recommended Focus:</strong> {misconceptionAnalysis.misconceptions[0].recommended_focus}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Concepts Demonstrated & Areas to Practice */}
          {((evaluation.concepts_demonstrated && evaluation.concepts_demonstrated.length > 0) ||
            (evaluation.concepts_missing && evaluation.concepts_missing.length > 0)) && (
            <div className="concept-rubric-breakdown">
              {evaluation.concepts_demonstrated && evaluation.concepts_demonstrated.length > 0 && (
                <div className="rubric-group demonstrated">
                  <span className="rubric-label">✓ What You Showed:</span>
                  <div className="rubric-tags">
                    {evaluation.concepts_demonstrated.map((c, i) => (
                      <span key={i} className="rubric-tag tag-demonstrated">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {evaluation.concepts_missing && evaluation.concepts_missing.length > 0 && (
                <div className="rubric-group missing">
                  <span className="rubric-label">Area to Review:</span>
                  <div className="rubric-tags">
                    {evaluation.concepts_missing.map((c, i) => (
                      <span key={i} className="rubric-tag tag-missing">{c}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
