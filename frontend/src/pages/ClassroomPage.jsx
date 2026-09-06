import React, { useState, useEffect } from 'react';
import { useClassroom, getStoredActiveSession } from '../context/ClassroomContext';
import TeacherStage from '../components/classroom/TeacherStage';
import Blackboard from '../components/classroom/Blackboard';
import LearningJourney from '../components/classroom/LearningJourney';
import ConceptProgress from '../components/classroom/ConceptProgress';
import LessonTimer from '../components/classroom/LessonTimer';
import ClassroomControls from '../components/classroom/ClassroomControls';
import QuestionPanel, { getAdaptiveActionInfo } from '../components/classroom/QuestionPanel';
import TeachingContent from '../components/classroom/TeachingContent';
import LoadingSpinner from '../components/LoadingSpinner';

/**
 * ClassroomPage Component
 * Premium AI Teacher Classroom Shell.
 * Integrates:
 * - Top Bar: AI Teacher, Topic, Current Concept, Progress, Time Remaining, Language
 * - Main Area: Large Teacher Stage (centerpiece) + Visual Blackboard + Learning Journey
 * - Bottom Area: Teacher transcript, interaction controls, question panel
 * - Session Recovery: "Continue where you left off" with clean concept & time preview without raw UUIDs
 * - Empty State: "Ready to learn something new?" with "Start Learning →"
 */
export default function ClassroomPage({ onNavigate }) {
  const {
    // Identity & Config
    sessionId,
    learnerId,
    topic,
    status,
    currentStep,
    completed,
    finalStatus,
    currentConceptId,
    currentConceptName,
    conceptIndex,
    totalConcepts,
    remainingTimeMinutes,
    language,
    preferredDifficulty,

    // Pedagogical Payloads
    delivery,
    question,
    evaluation,
    misconceptionAnalysis,
    adaptation,
    message,

    // Network & Operational Flags
    phase,
    loading,
    starting,
    advancing,
    submitting,
    switchingLanguage,
    ending,
    recovering,
    error,
    errorDetails,

    // Actions
    startClassroomSession,
    advanceTeachingStep,
    switchLanguage,
    refreshSession,
    endClassroomSession,
    resetClassroom,
    clearError,
    clearEvaluation,
  } = useClassroom();

  // Local transient state
  const [startTopic, setStartTopic] = useState('Data Structures and Algorithms');
  const [startLearner, setStartLearner] = useState('student_01');
  const [startDuration, setStartDuration] = useState(20);
  const [startDepth, setStartDepth] = useState('standard');
  const [startLang, setStartLang] = useState('english');
  const [startDifficulty, setStartDifficulty] = useState('beginner');
  const [resumeSessionId, setResumeSessionId] = useState('');
  const [showManualCodeInput, setShowManualCodeInput] = useState(false);
  const [learningPathOpen, setLearningPathOpen] = useState(false);

  // Check for auto-saved active session in localStorage for seamless recovery
  const [storedSession, setStoredSession] = useState(null);

  useEffect(() => {
    const saved = getStoredActiveSession();
    if (saved && saved.sessionId && saved.status !== 'completed') {
      setStoredSession(saved);
    }
  }, []);

  const handleLaunchSession = async (e) => {
    e.preventDefault();
    try {
      await startClassroomSession({
        learner_id: startLearner.trim() || 'student_01',
        topic: startTopic.trim() || 'Data Structures and Algorithms',
        available_time_minutes: Number(startDuration),
        desired_depth: startDepth,
        preferred_language: startLang,
        preferred_difficulty: startDifficulty,
      });
    } catch (err) {
      console.error('Session initialization error:', err);
    }
  };

  const handleResumeSavedSession = async () => {
    if (!storedSession?.sessionId) return;
    try {
      await refreshSession(storedSession.sessionId);
    } catch (err) {
      console.error('Saved session recovery failed:', err);
    }
  };

  const handleResumeManualSession = async (e) => {
    e.preventDefault();
    if (!resumeSessionId.trim()) return;
    try {
      await refreshSession(resumeSessionId.trim());
    } catch (err) {
      console.error('Manual session recovery error:', err);
    }
  };

  const hasActiveSession = Boolean(sessionId && status !== 'idle');
  const adaptiveActionInfo = adaptation ? getAdaptiveActionInfo(adaptation.action) : null;

  return (
    <div className="classroom-shell" id="ai-classroom-root">
      {/* 1. ROW 1 — CLASSROOM HEADER (Height: 64–72px) */}
      <header className="classroom-header-row1">
        {/* LEFT: Avatar thumbnail / teacher identity */}
        <div className="header-left-identity flex items-center gap-2.5">
          <div className="header-avatar-disc w-10 h-10 rounded-full bg-gradient-to-tr from-purple-100 to-indigo-100 border border-indigo-200 flex items-center justify-center text-xl flex-shrink-0 shadow-2xs">
            👩‍🏫
          </div>
          <div className="header-teacher-meta">
            <h2 className="header-teacher-name text-sm font-extrabold text-slate-900 leading-tight m-0">
              Professor Teachie
            </h2>
            <span className="header-live-badge text-[11px] font-bold text-indigo-700 flex items-center gap-1 leading-none mt-0.5">
              <span className="text-indigo-500 font-black text-xs">●</span>
              <span>{completed ? 'Lesson Complete' : status === 'active' ? 'Live Classroom' : 'Ready'}</span>
            </span>
          </div>
        </div>

        {/* MIDDLE: Topic → Current Concept */}
        <div className="header-middle-topic text-center px-4 max-w-lg hidden md:block">
          <div className="text-xs font-semibold text-slate-700 truncate">
            <span className="font-extrabold text-slate-900">{topic || 'Interactive Lesson'}</span>
            {currentConceptName && (
              <>
                <span className="mx-2 text-slate-400 font-normal">·</span>
                <span className="text-indigo-700 font-semibold">{currentConceptName}</span>
              </>
            )}
          </div>
        </div>

        {/* RIGHT: Language, Time remaining, Concept progress */}
        <div className="header-right-meta flex items-center gap-3">
          {hasActiveSession && (
            <>
              {/* Language Switcher Pill */}
              <div className="header-lang-pills flex items-center gap-1 bg-slate-100/90 p-0.5 rounded-xl border border-slate-200/80">
                {[
                  { id: 'english', label: 'English' },
                  { id: 'hindi', label: 'हिंदी' },
                  { id: 'hinglish', label: 'Hinglish' },
                ].map(({ id: lId, label: lLabel }) => (
                  <button
                    key={lId}
                    type="button"
                    className={`btn-lang-tab text-[11px] font-bold px-2 py-1 rounded-lg transition-all ${
                      language === lId
                        ? 'bg-white text-indigo-700 shadow-2xs font-extrabold'
                        : 'text-slate-600 hover:text-slate-900 bg-transparent'
                    }`}
                    onClick={() => switchLanguage(lId)}
                    disabled={switchingLanguage || language === lId}
                  >
                    {lLabel}
                  </button>
                ))}
              </div>

              {/* Time Remaining & Concept Progress */}
              <div className="header-stats-group text-right text-xs">
                <div className="header-time-rem font-bold text-slate-800">
                  {remainingTimeMinutes !== undefined ? `${remainingTimeMinutes} min remaining` : '20 min remaining'}
                </div>
                <div className="header-concept-prog text-[11px] text-slate-500 font-semibold">
                  {totalConcepts > 0 ? `${Math.min(conceptIndex + 1, totalConcepts)} / ${totalConcepts} concepts` : '1 / 5 concepts'}
                </div>
              </div>

              {/* Reset Session */}
              <button
                type="button"
                className="btn btn-icon btn-ghost text-slate-400 hover:text-slate-700 p-1.5 rounded-xl hover:bg-slate-100"
                onClick={resetClassroom}
                title="Reset classroom to start"
                aria-label="Reset classroom"
              >
                🔄
              </button>
            </>
          )}
        </div>
      </header>

      {/* 2. ROW 2 — PROGRESS (Thin progress section immediately below header) */}
      {hasActiveSession && (
        <section className="classroom-progress-row2" aria-label="Curriculum Progress">
          <div className="progress-info-bar flex items-center justify-between text-xs font-semibold text-slate-700 mb-1.5">
            <div className="flex items-center gap-2">
              <strong className="text-slate-900 font-bold">{currentConceptName || topic || 'Binary Tree Fundamentals'}</strong>
              <span className="text-slate-400">•</span>
              <span className="text-slate-600">
                Concept {Math.min(conceptIndex + 1, totalConcepts || 1)} of {totalConcepts || 1}
              </span>
            </div>
            <div className="progress-pct-badge font-bold text-indigo-700">
              {totalConcepts > 0 ? `${Math.round((Math.min(conceptIndex + 1, totalConcepts) / totalConcepts) * 100)}% complete` : '20% complete'}
            </div>
          </div>
          <div className="progress-track-bg">
            <div
              className="progress-track-fill-gradient"
              style={{
                width: `${totalConcepts > 0 ? Math.min(100, Math.round((Math.min(conceptIndex + 1, totalConcepts) / totalConcepts) * 100)) : 20}%`,
              }}
              role="progressbar"
              aria-valuenow={totalConcepts > 0 ? Math.round((Math.min(conceptIndex + 1, totalConcepts) / totalConcepts) * 100) : 20}
              aria-valuemin="0"
              aria-valuemax="100"
            />
          </div>
        </section>
      )}

      {/* 2. ERROR BANNER */}
      {error && (
        <div className="classroom-error-banner" role="alert">
          <div className="error-text-group flex items-center gap-3">
            <span className="error-icon text-xl">⚠️</span>
            <div>
              <strong className="error-title font-bold text-slate-800">Teacher notice: </strong>
              <span className="error-desc text-slate-700">We couldn't prepare this part right now. Please try again.</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() => {
                clearError();
                if (currentStep === 'question') {
                  const submitBtn = document.querySelector('.btn-submit-answer');
                  if (submitBtn) submitBtn.click();
                } else {
                  advanceTeachingStep();
                }
              }}
            >
              Try Again
            </button>
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={clearError}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* 3. MAIN STAGE CONTENT */}
      <main className="classroom-main-stage">
        {/* STATE A: NO ACTIVE SESSION (EMPTY STATE & RECOVERY) */}
        {!hasActiveSession && !starting && !recovering && (
          <div className="classroom-empty-launchpad">
            {/* Section 15: Classroom Empty State */}
            <div className="empty-classroom-hero">
              <div className="empty-hero-avatar-ring">
                <span className="hero-emoji">👩‍🏫</span>
              </div>
              <h1 className="hero-title">Ready to learn something new?</h1>
              <p className="hero-subtitle">
                Welcome to your personal AI Classroom. Your teacher adapts to your pace,
                demonstrates concepts visually, checks your understanding, and fixes misconceptions.
              </p>
              <div className="hero-cta-row">
                <button
                  type="button"
                  className="btn btn-primary btn-lg btn-start-learning"
                  onClick={() => onNavigate && onNavigate('setup')}
                >
                  Start Learning →
                </button>
              </div>
            </div>

            <div className="launchpad-grid">
              {/* Section 14: Session Recovery Card (If saved session exists) */}
              {storedSession && (
                <div className="launchpad-card recovery-card highlight-recovery">
                  <div className="launchpad-card-header">
                    <h3>🔁 Continue where you left off</h3>
                    <span className="badge badge-primary">Active Lesson</span>
                  </div>
                  <div className="recovery-preview-box">
                    <div className="recovery-row">
                      <span className="rec-label">Topic:</span>
                      <strong className="rec-val">{storedSession.topic || 'Current Lesson'}</strong>
                    </div>
                    {storedSession.currentConceptName && (
                      <div className="recovery-row">
                        <span className="rec-label">Current concept:</span>
                        <span className="rec-val">{storedSession.currentConceptName}</span>
                      </div>
                    )}
                    <div className="recovery-row">
                      <span className="rec-label">Progress:</span>
                      <span className="rec-val">
                        Concept {Math.min((storedSession.conceptIndex || 0) + 1, storedSession.totalConcepts || 1)} of{' '}
                        {storedSession.totalConcepts || 1}
                      </span>
                    </div>
                    {storedSession.remainingTimeMinutes !== undefined && (
                      <div className="recovery-row">
                        <span className="rec-label">Time remaining:</span>
                        <span className="rec-val">~{storedSession.remainingTimeMinutes} minutes</span>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary btn-block btn-lg mt-3"
                    onClick={handleResumeSavedSession}
                    disabled={loading || recovering}
                  >
                    {recovering ? (
                      <LoadingSpinner size="sm" text="Resuming Lesson..." inline color="text-white" />
                    ) : (
                      'Resume Lesson →'
                    )}
                  </button>
                </div>
              )}

              {/* Quick Launch Card */}
              <div className="launchpad-card">
                <div className="launchpad-card-header">
                  <h3>🚀 Quick Lesson Start</h3>
                  <span className="badge badge-secondary">Quick Setup</span>
                </div>
                <form onSubmit={handleLaunchSession} className="launch-form">
                  <div className="form-group">
                    <label htmlFor="topic-input">What would you like to learn?</label>
                    <input
                      id="topic-input"
                      type="text"
                      className="form-control"
                      value={startTopic}
                      onChange={(e) => setStartTopic(e.target.value)}
                      placeholder="e.g. Data Structures and Algorithms, Photosynthesis, French Revolution"
                      required
                    />
                  </div>

                  <div className="form-row">
                    <div className="form-group flex-1">
                      <label htmlFor="duration-select">Available Time</label>
                      <select
                        id="duration-select"
                        className="form-control"
                        value={startDuration}
                        onChange={(e) => setStartDuration(e.target.value)}
                      >
                        <option value="10">10 Minutes (Brief)</option>
                        <option value="20">20 Minutes (Standard)</option>
                        <option value="35">35 Minutes (Comprehensive)</option>
                      </select>
                    </div>

                    <div className="form-group flex-1">
                      <label htmlFor="lang-select">Language</label>
                      <select
                        id="lang-select"
                        className="form-control"
                        value={startLang}
                        onChange={(e) => setStartLang(e.target.value)}
                      >
                        <option value="english">English</option>
                        <option value="hindi">Hindi (हिंदी)</option>
                        <option value="hinglish">Hinglish</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group flex-1">
                      <label htmlFor="diff-select">Difficulty</label>
                      <select
                        id="diff-select"
                        className="form-control"
                        value={startDifficulty}
                        onChange={(e) => setStartDifficulty(e.target.value)}
                      >
                        <option value="beginner">Beginner</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                      </select>
                    </div>

                    <div className="form-group flex-1">
                      <label htmlFor="depth-select">Depth</label>
                      <select
                        id="depth-select"
                        className="form-control"
                        value={startDepth}
                        onChange={(e) => setStartDepth(e.target.value)}
                      >
                        <option value="quick_overview">Quick Overview</option>
                        <option value="standard">Standard</option>
                        <option value="deep_dive">Deep Dive</option>
                      </select>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-block btn-lg"
                    disabled={loading || starting}
                  >
                    {starting ? (
                      <LoadingSpinner size="sm" text="Preparing Your Teacher..." inline color="text-white" />
                    ) : (
                      'Enter AI Classroom →'
                    )}
                  </button>
                </form>

                <div className="manual-resume-toggle">
                  <button
                    type="button"
                    className="btn btn-xs btn-link"
                    onClick={() => setShowManualCodeInput(!showManualCodeInput)}
                  >
                    {showManualCodeInput ? '▲ Hide code input' : '🔑 Have a lesson code? Enter here'}
                  </button>
                  {showManualCodeInput && (
                    <form onSubmit={handleResumeManualSession} className="manual-resume-form mt-2">
                      <div className="input-group">
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={resumeSessionId}
                          onChange={(e) => setResumeSessionId(e.target.value)}
                          placeholder="e.g. ses_12345678"
                          required
                        />
                        <button
                          type="submit"
                          className="btn btn-secondary btn-sm"
                          disabled={recovering}
                        >
                          {recovering ? <LoadingSpinner size="sm" inline color="text-slate-600" /> : 'Resume'}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STATE B: STARTING / PREPARING LESSON */}
        {(starting || (loading && !delivery && !hasActiveSession)) && (
          <div className="classroom-loading-experience">
            <div className="empty-hero-avatar-ring animate-pulse mb-2">
              <span className="hero-emoji">👩‍🏫</span>
            </div>
            <h2 className="loading-teacher-title text-base font-extrabold text-slate-800 m-0">Professor Teachie</h2>
            <div className="my-2">
              <span className="teacher-state-badge badge-thinking inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                <span className="text-indigo-500">●</span> Preparing your lesson
              </span>
            </div>
            <LoadingSpinner
              size="large"
              text="Your personalized lesson is being prepared…"
              color="text-indigo-500"
            />
            <p className="loading-subtitle text-xs text-slate-500 mt-2 max-w-sm text-center">
              Calibrating curriculum, preparing visual demonstrations, and tuning adaptive checkpoints.
            </p>
          </div>
        )}

        {/* STATE C: ACTIVE TEACHING SESSION (Rendered strictly when not completed) */}
        {hasActiveSession && !completed && (
          <div className="classroom-session-content">
            {/* ROW 3 — MAIN CLASSROOM TWO-COLUMN GRID */}
            <div className="classroom-main-grid-row3">
              {/* LEFT COLUMN: AI TEACHER STAGE CARD */}
              <div className="teacher-column-42">
                <TeacherStage
                  delivery={delivery}
                  currentStep={currentStep}
                  status={status}
                  loading={loading}
                  advancing={advancing}
                  currentConceptName={currentConceptName}
                />
              </div>

              {/* RIGHT COLUMN: TEACHING CONTENT SURFACE OR QUESTION */}
              <div className="content-column-58">
                {Boolean(question || evaluation || currentStep === 'question') ? (
                  <QuestionPanel />
                ) : (
                  <TeachingContent
                    delivery={delivery}
                    currentStep={currentStep}
                    onAdvance={advanceTeachingStep}
                    advancing={advancing}
                    isBusy={loading}
                    currentConceptName={currentConceptName}
                    topic={topic}
                  />
                )}
              </div>
            </div>

            {/* Learning Path (Docked secondary below main cards, height: 80-120px) */}
            <div className="classroom-path-section">
              <LearningJourney compact={true} />
            </div>

            {/* STICKY/FIXED BOTTOM ACTION BAR (Height: 64px) */}
            <div className="classroom-bottom-action-bar">
              <div className="bottom-bar-left">
                <button
                  type="button"
                  className="btn-bottom-end text-xs font-bold text-slate-600 hover:text-rose-700 px-3.5 py-2 rounded-xl border border-slate-200 bg-white/80 hover:bg-rose-50 transition-all cursor-pointer"
                  onClick={() => {
                    if (window.confirm('Are you sure you want to conclude this lesson?')) {
                      endClassroomSession('completed');
                    }
                  }}
                  disabled={ending || loading}
                >
                  {ending ? 'Concluding...' : '⏹ End Lesson'}
                </button>
              </div>

              <div className="bottom-bar-center hidden sm:flex items-center gap-2 text-xs font-bold text-slate-700">
                <span className="w-2 h-2 rounded-full bg-indigo-600 inline-block" />
                <span>
                  {currentStep === 'demonstrate'
                    ? 'Step 2 · Demonstration'
                    : currentStep === 'question'
                    ? 'Step 3 · Check Understanding'
                    : 'Step 1 · Core Concept'}
                </span>
              </div>

              <div className="bottom-bar-right">
                {currentStep === 'question' ? (
                  <button
                    type="button"
                    className="btn-bottom-primary px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm hover:shadow transition-all cursor-pointer"
                    onClick={() => {
                      if (evaluation) {
                        if (typeof clearEvaluation === 'function') {
                          clearEvaluation();
                        }
                      } else {
                        const submitBtn = document.querySelector('.btn-submit-answer');
                        if (submitBtn) submitBtn.click();
                      }
                    }}
                    disabled={loading || submitting || advancing}
                  >
                    {evaluation
                      ? (adaptiveActionInfo?.buttonLabel || 'Continue with Teacher →')
                      : submitting
                      ? 'Professor Teachie is reviewing…'
                      : 'Check Answer →'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-bottom-primary px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm hover:shadow transition-all flex items-center gap-2 cursor-pointer"
                    onClick={() => advanceTeachingStep()}
                    disabled={advancing || loading}
                  >
                    {advancing ? (
                      <LoadingSpinner size="sm" text="Advancing..." inline color="text-white" />
                    ) : currentStep === 'demonstrate' ? (
                      <>
                        <span>Continue to Question</span>
                        <span aria-hidden="true">→</span>
                      </>
                    ) : (
                      <>
                        <span>Continue to Demonstration</span>
                        <span aria-hidden="true">→</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* STATE H: SESSION COMPLETED EXPERIENCE (Replaces teaching grid & bottom bar) */}
        {completed && (
          <div className="classroom-completed-experience">
            <div className="empty-hero-avatar-ring mb-3">
              <span className="hero-emoji">🎓</span>
            </div>
            <div className="text-center mb-2">
              <span className="teacher-state-badge badge-encouraging inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="text-emerald-500">●</span> Lesson complete
              </span>
            </div>
            <h2 className="completed-title">🎉 Lesson Complete!</h2>
            <p className="completed-desc">
              You have successfully completed all planned concepts for{' '}
              <strong className="text-slate-900 font-bold">{topic || 'this interactive lesson'}</strong>.
              Professor Teachie has updated your learning mastery profile.
            </p>
            <div className="completed-stats-row">
              <div className="stat-card">
                <span className="stat-num">{totalConcepts || 1}</span>
                <span className="stat-label">Concepts Covered</span>
              </div>
              <div className="stat-card">
                <span className="stat-num">100%</span>
                <span className="stat-label">Curriculum Mastered</span>
              </div>
              <div className="stat-card">
                <span className="stat-num capitalize">{language || 'English'}</span>
                <span className="stat-label">Instruction Language</span>
              </div>
            </div>
            <div className="completed-actions-row">
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={() => onNavigate && onNavigate('final-assessment')}
              >
                Start Final Assessment →
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-lg"
                onClick={() => onNavigate && onNavigate('revision')}
              >
                View Revision Dashboard
              </button>
              <button
                type="button"
                className="btn btn-outline btn-lg"
                onClick={() => {
                  resetClassroom();
                  if (onNavigate) onNavigate('setup');
                }}
              >
                Start Another Lesson
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
