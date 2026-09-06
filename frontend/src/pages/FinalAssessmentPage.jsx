import React, { useState, useEffect, useCallback } from 'react';
import { useClassroom } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

/**
 * FinalAssessmentPage Component
 * Student-friendly assessment experience.
 * Features a welcoming entry screen ("Check What You've Learned"),
 * step-by-step questions without answer leakage, and direct submission
 * to backend diagnostic evaluation.
 */
export default function FinalAssessmentPage({ onNavigate }) {
  const {
    sessionId,
    learnerId,
    lessonId,
    topic,
    preferredDifficulty,
    language,
    currentConceptId,
    assessmentPackage,
    setAssessmentPackage,
    setAssessmentReport,
  } = useClassroom();
  const { session: testSession } = useTestSession() || { session: {} };

  const effectiveLearnerId = learnerId || testSession?.learnerId || 'learner_01';

  // Local State
  const [hasStartedExam, setHasStartedExam] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [currentIdx, setCurrentIdx] = useState(0);

  // Student Answers Map: { [question_id]: { selected_option, answer_text, reasoning } }
  const [answers, setAnswers] = useState({});

  // Optional thought process accordion toggle
  const [showReasoning, setShowReasoning] = useState(false);

  // Function to load or generate assessment package with retry support
  const loadAssessment = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pkg = await api.generateFinalAssessment({
        learner_id: effectiveLearnerId,
        session_id: sessionId || null,
        lesson_id: lessonId || null,
        concept_ids: currentConceptId ? [currentConceptId] : [],
        difficulty: preferredDifficulty || 'intermediate',
        language: language || 'english',
        num_questions: 5,
      });

      setAssessmentPackage(pkg);
      setCurrentIdx(0);
      setAnswers({});
    } catch (err) {
      setError(err.message || 'Something went wrong while preparing your assessment questions.');
    } finally {
      setLoading(false);
    }
  }, [
    effectiveLearnerId,
    sessionId,
    lessonId,
    currentConceptId,
    preferredDifficulty,
    language,
    setAssessmentPackage,
  ]);

  // Preload questions when student enters
  useEffect(() => {
    if (!assessmentPackage || !assessmentPackage.questions || assessmentPackage.questions.length === 0) {
      loadAssessment();
    }
  }, [assessmentPackage, loadAssessment]);

  const questions = assessmentPackage?.questions || [];
  const currentQ = questions[currentIdx];
  const isLastQuestion = currentIdx === questions.length - 1;

  // Question Answer Getters & Setters
  const currentAnswer = currentQ ? (answers[currentQ.question_id] || {}) : {};

  const handleSelectOption = (opt) => {
    if (!currentQ || submitting) return;
    setAnswers((prev) => ({
      ...prev,
      [currentQ.question_id]: {
        ...prev[currentQ.question_id],
        selected_option: opt,
      },
    }));
  };

  const handleTextChange = (text) => {
    if (!currentQ || submitting) return;
    setAnswers((prev) => ({
      ...prev,
      [currentQ.question_id]: {
        ...prev[currentQ.question_id],
        answer_text: text,
      },
    }));
  };

  const handleReasoningChange = (reasoningText) => {
    if (!currentQ || submitting) return;
    setAnswers((prev) => ({
      ...prev,
      [currentQ.question_id]: {
        ...prev[currentQ.question_id],
        reasoning: reasoningText,
      },
    }));
  };

  const handlePrev = () => {
    if (currentIdx > 0) {
      setCurrentIdx((idx) => idx - 1);
      setShowReasoning(false);
    }
  };

  const handleNext = () => {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx((idx) => idx + 1);
      setShowReasoning(false);
    }
  };

  const handleSubmitExam = async () => {
    if (!assessmentPackage || submitting) return;

    setError(null);
    setSubmitting(true);

    try {
      const submissionPayload = {
        assessment_id: assessmentPackage.assessment_id,
        learner_id: assessmentPackage.learner_id || effectiveLearnerId,
        session_id: assessmentPackage.session_id || sessionId || null,
        lesson_id: assessmentPackage.lesson_id || lessonId || null,
        answers: assessmentPackage.questions.map((q) => {
          const ans = answers[q.question_id] || {};
          return {
            question_id: q.question_id,
            selected_option: ans.selected_option || null,
            answer_text: ans.answer_text ? ans.answer_text.trim() : null,
            reasoning: ans.reasoning ? ans.reasoning.trim() : null,
          };
        }),
        language: language || 'english',
      };

      const report = await api.evaluateFinalAssessment(submissionPayload);
      setAssessmentReport(report);

      if (typeof onNavigate === 'function') {
        onNavigate('assessment-results');
      }
    } catch (err) {
      setError(err.message || 'Failed to submit final assessment. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const isMCQ = currentQ?.question_type === 'mcq' || (currentQ?.options && currentQ.options.length > 0);

  // Normalize Question Type Label
  const formatQuestionType = (type) => {
    switch (type) {
      case 'mcq':
        return 'Multiple Choice';
      case 'short_answer':
        return 'Short Answer';
      case 'conceptual':
        return 'Conceptual Analysis';
      case 'application':
        return 'Problem Solving & Application';
      default:
        return 'Assessment Question';
    }
  };

  return (
    <div className="final-assessment-container">
      {/* Assessment Header */}
      <header className="assessment-header">
        <div className="assessment-title-group">
          <span className="exam-icon" aria-hidden="true">📝</span>
          <div>
            <h1 className="assessment-title">
              {hasStartedExam ? 'Final Assessment' : "Check What You've Learned"}
            </h1>
            <p className="assessment-subtitle">
              {hasStartedExam
                ? 'Verify your mastery across all concepts you learned with your AI Teacher'
                : 'Take a quick check to see what you understand well and where you can improve'}
            </p>
          </div>
        </div>

        {hasStartedExam && questions.length > 0 && (
          <div className="assessment-progress-badge">
            Question {currentIdx + 1} of {questions.length}
          </div>
        )}
      </header>

      {/* Progress Bar (Visible during exam) */}
      {hasStartedExam && questions.length > 0 && (
        <div
          className="assessment-progress-track"
          role="progressbar"
          aria-valuenow={currentIdx + 1}
          aria-valuemin={1}
          aria-valuemax={questions.length}
        >
          <div
            className="assessment-progress-fill"
            style={{ width: `${((currentIdx + 1) / questions.length) * 100}%` }}
          />
        </div>
      )}

      {/* Error Alert with Retry Action */}
      {error && (
        <div className="assessment-error-alert" role="alert">
          <span className="alert-icon">⚠️</span>
          <span className="alert-text">
            {error.includes('502') || error.includes('Failed to generate')
              ? 'Something went wrong while preparing your assessment questions.'
              : error}
          </span>
          <div className="alert-actions">
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={loadAssessment}
            >
              Try Again
            </button>
            <button
              type="button"
              className="btn btn-xs btn-link"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="assessment-loading-box">
          <LoadingSpinner size="large" text="Preparing your assessment..." color="text-indigo-500" />
          <p className="loading-desc">
            Your AI Teacher is designing check questions tailored to your lesson topic.
          </p>
        </div>
      )}

      {/* Entry Screen (Before starting) */}
      {!hasStartedExam && !loading && (
        <div className="assessment-entry-card">
          <div className="entry-icon-circle">
            <span>🎓</span>
          </div>
          <h2 className="entry-heading">Ready to see what you've learned?</h2>
          <p className="entry-description">
            Answer a few quick questions to demonstrate your conceptual grasp.
            Your AI Teacher will analyze your mental model and produce a personalized learning report.
          </p>

          <div className="entry-details-grid">
            <div className="entry-detail-item">
              <span className="detail-label">Subject / Topic</span>
              <strong className="detail-val">{topic || 'Current Curriculum'}</strong>
            </div>
            <div className="entry-detail-item">
              <span className="detail-label">Total Questions</span>
              <strong className="detail-val">{questions.length || 5} Questions</strong>
            </div>
            <div className="entry-detail-item">
              <span className="detail-label">Estimated Time</span>
              <strong className="detail-val">~10 Minutes</strong>
            </div>
            <div className="entry-detail-item">
              <span className="detail-label">Difficulty</span>
              <strong className="detail-val capitalize">{preferredDifficulty || 'Standard'}</strong>
            </div>
          </div>

          <div className="entry-action-row">
            <button
              type="button"
              className="btn btn-primary btn-lg btn-pill shadow-soft"
              onClick={() => {
                setHasStartedExam(true);
                if (questions.length === 0) loadAssessment();
              }}
            >
              Start Assessment →
            </button>
          </div>
        </div>
      )}

      {/* Active Question Card */}
      {hasStartedExam && !loading && currentQ && (
        <div className="assessment-question-card">
          {/* Question Metadata Header */}
          <div className="q-card-header">
            <div className="q-type-tags">
              <span className="badge badge-primary">
                {formatQuestionType(currentQ.question_type)}
              </span>
              {currentQ.difficulty && (
                <span className="badge badge-secondary capitalize">
                  {currentQ.difficulty}
                </span>
              )}
            </div>
            <span className="q-number-tag">
              Q{currentIdx + 1}
            </span>
          </div>

          {/* Question Prompt */}
          <div className="q-prompt-box">
            <p className="q-prompt-text">{currentQ.question_text}</p>
            {currentQ.learning_objective && (
              <span className="learning-objective-tag">
                🎯 Tested Objective: {currentQ.learning_objective}
              </span>
            )}
          </div>

          {/* Answer Controls */}
          <div className="q-answer-container">
            {isMCQ ? (
              /* MCQ Radio Options */
              <fieldset className="mcq-options-fieldset" disabled={submitting}>
                <legend className="sr-only">Select one option</legend>
                <div className="mcq-options-list">
                  {currentQ.options.map((opt, i) => {
                    const letter = String.fromCharCode(65 + i);
                    const isChecked = currentAnswer.selected_option === opt;

                    return (
                      <label
                        key={i}
                        className={`mcq-option-label ${isChecked ? 'selected' : ''}`}
                      >
                        <input
                          type="radio"
                          name={`final_q_${currentQ.question_id}`}
                          value={opt}
                          checked={isChecked}
                          onChange={() => handleSelectOption(opt)}
                          disabled={submitting}
                          className="mcq-radio-input"
                        />
                        <span className="opt-letter">{letter}</span>
                        <span className="opt-text">{opt}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ) : (
              /* Free-Text / Open-Ended Working */
              <div className="free-text-input-group">
                <label htmlFor={`free_text_${currentQ.question_id}`} className="input-label">
                  Your Answer or Solution:
                </label>
                <textarea
                  id={`free_text_${currentQ.question_id}`}
                  className="form-control question-textarea"
                  rows={4}
                  value={currentAnswer.answer_text || ''}
                  onChange={(e) => handleTextChange(e.target.value)}
                  disabled={submitting}
                  placeholder="Type your explanation or worked answer here..."
                />
              </div>
            )}

            {/* Optional Thought Process Disclosure */}
            <div className="reasoning-toggle-container">
              <button
                type="button"
                className="btn-toggle-reasoning"
                onClick={() => setShowReasoning(!showReasoning)}
              >
                {showReasoning ? '▲ Hide Reasoning' : '💡 + Add your thought process (Optional)'}
              </button>

              {showReasoning && (
                <div className="reasoning-input-box">
                  <label htmlFor={`reasoning_${currentQ.question_id}`} className="reasoning-label">
                    Explain how you arrived at this answer (helps diagnose misconception vs slip):
                  </label>
                  <textarea
                    id={`reasoning_${currentQ.question_id}`}
                    className="form-control reasoning-textarea"
                    rows={2}
                    value={currentAnswer.reasoning || ''}
                    onChange={(e) => handleReasoningChange(e.target.value)}
                    disabled={submitting}
                    placeholder="e.g. I deduced this because..."
                  />
                </div>
              )}
            </div>
          </div>

          {/* Navigation Controls */}
          <footer className="assessment-navigation-bar">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handlePrev}
              disabled={currentIdx === 0 || submitting}
            >
              ← Previous Question
            </button>

            <div className="q-nav-dots">
              {questions.map((q, idx) => {
                const isAnswered = Boolean(
                  answers[q.question_id]?.selected_option ||
                  answers[q.question_id]?.answer_text?.trim()
                );
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`q-nav-dot ${idx === currentIdx ? 'active' : ''} ${isAnswered ? 'answered' : ''}`}
                    onClick={() => setCurrentIdx(idx)}
                    title={`Question ${idx + 1} (${isAnswered ? 'Answered' : 'Unanswered'})`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>

            {isLastQuestion ? (
              <button
                type="button"
                className="btn btn-primary btn-submit-exam"
                onClick={handleSubmitExam}
                disabled={submitting}
              >
                {submitting ? (
                  <LoadingSpinner size="sm" text="Evaluating Answers..." inline color="text-white" />
                ) : (
                  'Submit Final Assessment →'
                )}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleNext}
                disabled={submitting}
              >
                Next Question →
              </button>
            )}
          </footer>
        </div>
      )}

      {/* Empty State / Fallback with direct generation action */}
      {!loading && questions.length === 0 && (
        <div className="assessment-empty-state">
          <span className="empty-icon">📭</span>
          <h3>No Assessment Questions Loaded</h3>
          <p>You can generate an assessment now for your current session or launch a new lesson.</p>
          <div className="empty-actions-row">
            <button
              type="button"
              className="btn btn-primary"
              onClick={loadAssessment}
            >
              Generate Final Assessment
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onNavigate && onNavigate('setup')}
            >
              Go to Setup Wizard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
