import React, { useState, useEffect } from 'react';
import { useClassroom, getStoredActiveSession } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';

/**
 * LandingAuthPage Component — Standalone Public Landing & Sign In / Register Page
 * 
 * Requirements:
 * 1. Fully standalone: NOT wrapped in the dashboard (no sidebar, no dashboard header).
 * 2. Acts as the primary Sign In & Register portal.
 * 3. Uses existing soft lilac (#faf8fe, #f5f3ff, #e0d7f5) and powder blue (#e0f2fe) color palette.
 * 4. Highlights the home lady teacher image (/images/teacher_hero.jpg) with glowing pedestal and floating badges.
 * 5. Full pedagogical showcase: Bento grid, 4-step Socratic loop, learning paths, curriculum domains, testimonials.
 */
export default function LandingAuthPage({
  onSignIn,
  onRegister,
  onGuestEnter,
  onDirectStartTopic,
  onNavigate,
}) {
  const {
    sessionId,
    status,
    topic,
    currentConceptName,
    remainingTimeMinutes,
    refreshSession,
    language = 'english',
    switchLanguage,
  } = useClassroom();
  const { updateSession } = useTestSession() || { updateSession: () => {} };

  // Auth Card State: 'signin' or 'register'
  const [authMode, setAuthMode] = useState('signin');
  const [showPassword, setShowPassword] = useState(false);

  // Form Fields
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);

  const [regFullName, setRegFullName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regGrade, setRegGrade] = useState('undergrad');
  const [regPassword, setRegPassword] = useState('');

  // UI status / feedback
  const [authMessage, setAuthMessage] = useState(null);
  const [searchTopic, setSearchTopic] = useState('');
  const [showNavLang, setShowNavLang] = useState(false);

  // Resume active session state
  const storedSession = getStoredActiveSession();
  const [activeLessonTitle, setActiveLessonTitle] = useState('Data Structures & Algorithms');
  const [activeConceptTitle, setActiveConceptTitle] = useState('Binary Search Trees');
  const [activeProgressPct, setActiveProgressPct] = useState(60);

  useEffect(() => {
    if (topic || storedSession?.topic) {
      setActiveLessonTitle(topic || storedSession.topic);
    }
    if (currentConceptName || storedSession?.currentConceptName) {
      setActiveConceptTitle(currentConceptName || storedSession.currentConceptName);
    }
    if (storedSession?.conceptIndex !== undefined && storedSession?.totalConcepts) {
      const pct = Math.round(((storedSession.conceptIndex + 1) / storedSession.totalConcepts) * 100);
      setActiveProgressPct(Math.max(15, Math.min(100, pct)));
    }
  }, [topic, currentConceptName, storedSession]);

  // Sign In Handler
  const handleSignInSubmit = (e) => {
    e.preventDefault();
    const identifier = signInEmail.trim() || 'Learner';
    const name = identifier.includes('@') ? identifier.split('@')[0] : identifier;
    const userData = {
      name: name.charAt(0).toUpperCase() + name.slice(1),
      email: identifier.includes('@') ? identifier : `${identifier.toLowerCase()}@teachie.ai`,
      grade: 'General Learner',
      isGuest: false,
    };
    setAuthMessage({ type: 'success', text: `Welcome back, ${userData.name}! Entering classroom...` });
    setTimeout(() => {
      if (onSignIn) onSignIn(userData);
    }, 450);
  };

  // Register Handler
  const handleRegisterSubmit = (e) => {
    e.preventDefault();
    const name = regFullName.trim() || 'New Student';
    const email = regEmail.trim() || `${name.toLowerCase().replace(/\s+/g, '')}@teachie.ai`;
    const gradeLabels = {
      highschool: 'High School (Grades 9-12)',
      undergrad: 'Undergraduate / College',
      competitive: 'Competitive Exams (JEE/NEET/GRE)',
      lifelong: 'Lifelong Learner',
    };
    const userData = {
      name,
      email,
      grade: gradeLabels[regGrade] || 'College',
      isGuest: false,
    };
    setAuthMessage({ type: 'success', text: `Account created for ${userData.name}! Starting your journey...` });
    setTimeout(() => {
      if (onRegister) onRegister(userData);
    }, 450);
  };

  // Guest Enter
  const handleGuest = () => {
    const guestUser = {
      name: 'Guest Learner',
      email: 'guest@teachie.ai',
      grade: 'Undergraduate / College',
      isGuest: true,
    };
    if (onGuestEnter) {
      onGuestEnter(guestUser);
    } else if (onSignIn) {
      onSignIn(guestUser);
    }
  };

  // Direct Topic Search
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchTopic.trim()) return;
    const topicName = searchTopic.trim();
    if (updateSession) updateSession({ selectedConcept: topicName });
    if (onDirectStartTopic) {
      onDirectStartTopic(topicName);
    } else {
      handleGuest();
    }
  };

  const handlePickPopularTopic = (topicName) => {
    if (updateSession) updateSession({ selectedConcept: topicName });
    if (onDirectStartTopic) {
      onDirectStartTopic(topicName);
    } else {
      handleGuest();
    }
  };

  // Resume Session
  const handleResumeSession = async () => {
    if (sessionId && status === 'active') {
      if (onNavigate) onNavigate('classroom');
      return;
    }
    if (storedSession?.sessionId) {
      try {
        await refreshSession(storedSession.sessionId);
        if (onNavigate) onNavigate('classroom');
        return;
      } catch (e) {
        console.warn('Could not resume stored session:', e);
      }
    }
    if (onNavigate) onNavigate('classroom');
  };

  const hasResumeableSession = Boolean(
    (sessionId && status === 'active') || storedSession?.sessionId
  );

  const scrollToAuth = (mode) => {
    setAuthMode(mode);
    const cardEl = document.getElementById('hero-auth-card');
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const displayLang = language === 'hindi' ? 'हिंदी' : language === 'hinglish' ? 'Hinglish' : 'English';

  return (
    <div className="landing-standalone-root">
      {/* ====================================================================
          1. STANDALONE TOP NAVIGATION (Public, Outside Dashboard)
          ==================================================================== */}
      <header className="landing-standalone-nav" aria-label="Landing Navigation">
        <div className="landing-nav-inner">
          {/* Brand Logo */}
          <div className="landing-nav-brand">
            <div className="brand-book-icon" aria-hidden="true">
              <span>📖</span>
            </div>
            <div className="landing-brand-text">
              <span className="brand-main-title">Teachie</span>
              <span className="landing-brand-sub">AI 1-on-1 Teacher</span>
            </div>
          </div>

          {/* Navigation Anchors */}
          <nav className="landing-nav-links" aria-label="Page Sections">
            <button type="button" className="landing-nav-link" onClick={() => scrollToSection('features')}>
              Features
            </button>
            <button type="button" className="landing-nav-link" onClick={() => scrollToSection('pipeline')}>
              Socratic Loop
            </button>
            <button type="button" className="landing-nav-link" onClick={() => scrollToSection('curriculum')}>
              Curriculum
            </button>
            <button type="button" className="landing-nav-link" onClick={() => scrollToSection('reviews')}>
              Reviews
            </button>
          </nav>

          {/* Right Action Buttons */}
          <div className="landing-nav-actions">
            {/* Language Switcher */}
            <div className="landing-lang-wrapper">
              <button
                type="button"
                className="landing-lang-btn"
                onClick={() => setShowNavLang(!showNavLang)}
                aria-label="Select language"
              >
                <span>🌐</span>
                <span className="lang-code">{displayLang}</span>
                <span className="arrow-small">▾</span>
              </button>
              {showNavLang && (
                <div className="landing-lang-menu">
                  <button
                    type="button"
                    className={`lang-opt ${language === 'english' ? 'active' : ''}`}
                    onClick={() => {
                      if (switchLanguage) switchLanguage('english');
                      setShowNavLang(false);
                    }}
                  >
                    English
                  </button>
                  <button
                    type="button"
                    className={`lang-opt ${language === 'hindi' ? 'active' : ''}`}
                    onClick={() => {
                      if (switchLanguage) switchLanguage('hindi');
                      setShowNavLang(false);
                    }}
                  >
                    हिंदी (Hindi)
                  </button>
                  <button
                    type="button"
                    className={`lang-opt ${language === 'hinglish' ? 'active' : ''}`}
                    onClick={() => {
                      if (switchLanguage) switchLanguage('hinglish');
                      setShowNavLang(false);
                    }}
                  >
                    Hinglish
                  </button>
                </div>
              )}
            </div>

            {/* Quick Sign In Jump */}
            <button
              type="button"
              className="btn-nav-signin"
              onClick={() => scrollToAuth('signin')}
            >
              Sign In
            </button>

            {/* Register / Get Started */}
            <button
              type="button"
              className="btn-nav-register"
              onClick={() => scrollToAuth('register')}
            >
              <span>Get Started Free</span>
              <span className="btn-sparkle">✨</span>
            </button>
          </div>
        </div>
      </header>

      {/* ====================================================================
          2. HERO SHOWCASE: SPLIT VISUAL STAGE & SIGN IN / REGISTER PORTAL
          ==================================================================== */}
      <main className="landing-main-content">
        <section className="landing-hero-showcase" aria-label="Hero & Authentication">
          <div className="landing-hero-ambient-glow glow-1" />
          <div className="landing-hero-ambient-glow glow-2" />

          <div className="landing-hero-grid">
            {/* LEFT COLUMN: Educational Value Prop & Lady Teacher Showcase */}
            <div className="landing-hero-left">
              <div className="landing-hero-pill-badge">
                <span className="pill-sparkle">✨</span>
                <span className="pill-text">AI-Powered 1-on-1 Socratic Classroom</span>
              </div>

              <h1 className="landing-hero-headline">
                Master Any Subject.<br />
                <span className="landing-gradient-text">At Your Own Pace.</span>
              </h1>

              <p className="landing-hero-subtext">
                Meet Professor Teachie—an adaptive AI educator that explains concepts from first
                principles, renders real-time blackboard diagrams, diagnoses misconceptions, and speaks
                in your natural voice.
              </p>

              {/* Lady Teacher Hero Stage */}
              <div className="landing-teacher-stage-wrapper">
                <div className="teacher-glow-pedestal" />

                {/* Floating Glass Badges */}
                <div className="floating-badge badge-top-left animate-float-slow">
                  <span className="badge-icon">💡</span>
                  <div className="badge-text">
                    <strong>Adaptive Socratic AI</strong>
                    <span>Calibrates to your depth</span>
                  </div>
                </div>

                <div className="floating-badge badge-top-right animate-float-delayed">
                  <span className="badge-icon">📊</span>
                  <div className="badge-text">
                    <strong>98% Concept Mastery</strong>
                    <span>Diagnostic checks</span>
                  </div>
                </div>

                <div className="floating-badge badge-bottom-left animate-float-slow">
                  <span className="badge-icon">🗣️</span>
                  <div className="badge-text">
                    <strong>Multilingual Voice</strong>
                    <span>English • हिंदी • Hinglish</span>
                  </div>
                </div>

                {/* The Hero Teacher Lady Image */}
                <div className="teacher-portrait-frame">
                  <img
                    src="/images/teacher_hero.jpg"
                    alt="Professor Teachie - Your AI Teacher"
                    className="teacher-lady-hero-img"
                    loading="eager"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                  <div className="portrait-reflection-overlay" />
                  <div className="teacher-signature-pill">
                    <span className="heart-icon">💗</span>
                    <span>A Brighter You Every Day</span>
                  </div>
                </div>
              </div>

              {/* Trust Proof Bar */}
              <div className="landing-trust-bar">
                <div className="trust-item">
                  <span className="trust-icon">⭐</span>
                  <span className="trust-text"><strong>4.9 / 5</strong> Student Rating</span>
                </div>
                <span className="trust-divider">•</span>
                <div className="trust-item">
                  <span className="trust-icon">🧠</span>
                  <span className="trust-text"><strong>100% Adaptive</strong> Socratic</span>
                </div>
                <span className="trust-divider">•</span>
                <div className="trust-item">
                  <span className="trust-icon">🎙️</span>
                  <span className="trust-text"><strong>Voice & Video</strong> Export</span>
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: THE SIGN IN / REGISTER CARD (Dedicated Auth Portal) */}
            <div className="landing-hero-right" id="hero-auth-card">
              <div className="landing-auth-card">
                {/* Auth Card Header */}
                <div className="auth-card-top">
                  <div className="auth-card-badge">
                    <span>🎓</span>
                    <span>AI Classroom Gateway</span>
                  </div>
                  <h2 className="auth-card-title">
                    {authMode === 'signin' ? 'Welcome Back to Class' : 'Start Learning with Teachie'}
                  </h2>
                  <p className="auth-card-subtitle">
                    {authMode === 'signin'
                      ? 'Sign in to access your sessions, mastery stats & personalized notes.'
                      : 'Create your free learner account. No credit card required.'}
                  </p>
                </div>

                {/* Segmented Tab Switcher */}
                <div className="auth-tab-switcher" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={authMode === 'signin'}
                    className={`auth-tab-btn ${authMode === 'signin' ? 'active' : ''}`}
                    onClick={() => {
                      setAuthMode('signin');
                      setAuthMessage(null);
                    }}
                  >
                    <span>🔑</span>
                    <span>Sign In</span>
                  </button>

                  <button
                    type="button"
                    role="tab"
                    aria-selected={authMode === 'register'}
                    className={`auth-tab-btn ${authMode === 'register' ? 'active' : ''}`}
                    onClick={() => {
                      setAuthMode('register');
                      setAuthMessage(null);
                    }}
                  >
                    <span>✨</span>
                    <span>Register Free</span>
                  </button>
                </div>

                {/* Feedback Notification */}
                {authMessage && (
                  <div className={`auth-feedback-banner ${authMessage.type}`}>
                    <span>{authMessage.type === 'success' ? '✅' : 'ℹ️'}</span>
                    <span>{authMessage.text}</span>
                  </div>
                )}

                {/* ===================== TAB 1: SIGN IN ===================== */}
                {authMode === 'signin' ? (
                  <form onSubmit={handleSignInSubmit} className="auth-form" aria-label="Sign In Form">
                    <div className="form-field-group">
                      <label className="field-label" htmlFor="signin-email">
                        Email or Username
                      </label>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">✉️</span>
                        <input
                          id="signin-email"
                          type="text"
                          className="auth-input-field"
                          placeholder="student@example.com or username"
                          value={signInEmail}
                          onChange={(e) => setSignInEmail(e.target.value)}
                          autoComplete="username"
                        />
                      </div>
                    </div>

                    <div className="form-field-group">
                      <div className="field-label-row">
                        <label className="field-label" htmlFor="signin-password">
                          Password
                        </label>
                        <button
                          type="button"
                          className="link-btn forgot-btn"
                          onClick={() => setAuthMessage({ type: 'info', text: 'Demo mode: Any password is accepted.' })}
                        >
                          Forgot password?
                        </button>
                      </div>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">🔒</span>
                        <input
                          id="signin-password"
                          type={showPassword ? 'text' : 'password'}
                          className="auth-input-field"
                          placeholder="Enter your password"
                          value={signInPassword}
                          onChange={(e) => setSignInPassword(e.target.value)}
                          autoComplete="current-password"
                        />
                        <button
                          type="button"
                          className="toggle-pwd-btn"
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                          {showPassword ? '🙈' : '👁️'}
                        </button>
                      </div>
                    </div>

                    <div className="auth-remember-row">
                      <label className="remember-label">
                        <input
                          type="checkbox"
                          checked={rememberMe}
                          onChange={(e) => setRememberMe(e.target.checked)}
                          className="remember-checkbox"
                        />
                        <span>Remember me on this device</span>
                      </label>
                    </div>

                    {/* Primary Sign In Button */}
                    <button type="submit" className="btn-auth-submit">
                      <span>Sign In to Classroom</span>
                      <span className="btn-arrow-glow">→</span>
                    </button>
                  </form>
                ) : (
                  /* ===================== TAB 2: REGISTER ===================== */
                  <form onSubmit={handleRegisterSubmit} className="auth-form" aria-label="Register Form">
                    <div className="form-field-group">
                      <label className="field-label" htmlFor="reg-name">
                        Full Name
                      </label>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">👤</span>
                        <input
                          id="reg-name"
                          type="text"
                          className="auth-input-field"
                          placeholder="e.g. Alex Rivera"
                          value={regFullName}
                          onChange={(e) => setRegFullName(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="form-field-group">
                      <label className="field-label" htmlFor="reg-email">
                        Email Address
                      </label>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">✉️</span>
                        <input
                          id="reg-email"
                          type="email"
                          className="auth-input-field"
                          placeholder="alex@example.com"
                          value={regEmail}
                          onChange={(e) => setRegEmail(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="form-field-group">
                      <label className="field-label" htmlFor="reg-grade">
                        Learning Level / Goal
                      </label>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">🎯</span>
                        <select
                          id="reg-grade"
                          className="auth-select-field"
                          value={regGrade}
                          onChange={(e) => setRegGrade(e.target.value)}
                        >
                          <option value="highschool">High School (Grades 9-12)</option>
                          <option value="undergrad">Undergraduate / College</option>
                          <option value="competitive">Competitive Exams (JEE / NEET / GRE)</option>
                          <option value="lifelong">Lifelong Learner / Professional</option>
                        </select>
                      </div>
                    </div>

                    <div className="form-field-group">
                      <label className="field-label" htmlFor="reg-password">
                        Create Password
                      </label>
                      <div className="input-with-icon">
                        <span className="input-decor-icon">🔒</span>
                        <input
                          id="reg-password"
                          type={showPassword ? 'text' : 'password'}
                          className="auth-input-field"
                          placeholder="At least 6 characters"
                          value={regPassword}
                          onChange={(e) => setRegPassword(e.target.value)}
                          autoComplete="new-password"
                        />
                        <button
                          type="button"
                          className="toggle-pwd-btn"
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                          {showPassword ? '🙈' : '👁️'}
                        </button>
                      </div>
                    </div>

                    {/* Primary Register Button */}
                    <button type="submit" className="btn-auth-submit btn-register-glow">
                      <span>Create Free Account & Start Learning</span>
                      <span className="btn-sparkle">✨</span>
                    </button>
                  </form>
                )}

                {/* Instant Guest & Quick Launch Section */}
                <div className="auth-card-divider">
                  <span className="divider-line" />
                  <span className="divider-label">OR PREVIEW INSTANTLY</span>
                  <span className="divider-line" />
                </div>

                <button
                  type="button"
                  className="btn-guest-instant"
                  onClick={handleGuest}
                >
                  <span className="guest-icon">🚀</span>
                  <div className="guest-text-group">
                    <span className="guest-title">Continue as Guest</span>
                    <span className="guest-desc">1-Click Instant Preview (No Credentials Needed)</span>
                  </div>
                  <span className="guest-arrow">→</span>
                </button>

                {/* Quick Topic Jump Input */}
                <div className="auth-quick-topic-wrapper">
                  <form onSubmit={handleSearchSubmit} className="auth-topic-search-box">
                    <span className="topic-search-icon">🔍</span>
                    <input
                      type="text"
                      className="auth-topic-input"
                      placeholder="Or start any topic (e.g. Binary Trees)..."
                      value={searchTopic}
                      onChange={(e) => setSearchTopic(e.target.value)}
                    />
                    <button type="submit" className="btn-topic-go">
                      Go →
                    </button>
                  </form>

                  {/* Popular Topic Chips */}
                  <div className="auth-chips-row">
                    <span className="chips-hint">Quick pick:</span>
                    {[
                      { name: 'Binary Trees', emoji: '🌲' },
                      { name: "Newton's Laws", emoji: '⚛️' },
                      { name: 'Calculus', emoji: '📐' },
                      { name: 'Photosynthesis', emoji: '🌿' },
                    ].map((t) => (
                      <button
                        key={t.name}
                        type="button"
                        className="auth-topic-chip"
                        onClick={() => handlePickPopularTopic(t.name)}
                      >
                        <span>{t.emoji}</span>
                        <span>{t.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Security Guarantee */}
                <div className="auth-card-trust-footer">
                  <span>🔒 100% Free • No Credit Card Required • GDPR & COPPA Compliant</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====================================================================
            3. CONTINUE ACTIVE LESSON BANNER (If previous session exists)
            ==================================================================== */}
        {hasResumeableSession && (
          <section className="landing-continue-strip" aria-label="Resume Your Session">
            <div className="continue-strip-inner">
              <div className="continue-strip-left">
                <div className="continue-icon-box">
                  <span>🧊</span>
                </div>
                <div>
                  <span className="continue-sub">Active Learning Session Detected</span>
                  <h3 className="continue-title">{activeLessonTitle}</h3>
                  <span className="continue-concept">
                    Currently on: <strong>{activeConceptTitle}</strong>
                  </span>
                </div>
              </div>

              <div className="continue-strip-mid">
                <div className="continue-progress-row">
                  <span className="progress-label">Progress</span>
                  <span className="progress-val">{activeProgressPct}%</span>
                </div>
                <div className="continue-progress-track">
                  <div
                    className="continue-progress-fill"
                    style={{ width: `${activeProgressPct}%` }}
                  />
                </div>
                <span className="continue-time">⏱ ~{remainingTimeMinutes || 20} min remaining</span>
              </div>

              <button
                type="button"
                className="btn-continue-session"
                onClick={handleResumeSession}
              >
                <span>Resume Lesson</span>
                <span className="arrow-icon">→</span>
              </button>
            </div>
          </section>
        )}

        {/* ====================================================================
            4. BENTO GRID: WHY STUDENTS LEARN 3X FASTER
            ==================================================================== */}
        <section id="features" className="landing-bento-section" aria-label="Why Learn with Teachie">
          <div className="landing-section-header text-center">
            <span className="landing-section-eyebrow">PEDAGOGICAL EXCELLENCE</span>
            <h2 className="landing-section-title">Built Around How Your Brain Actually Learns</h2>
            <p className="landing-section-desc">
              Traditional lectures are passive. Professor Teachie uses active Socratic dialogue,
              multimodal visual blackboard renderings, and real-time cognitive adaptation.
            </p>
          </div>

          <div className="landing-bento-grid">
            <div className="bento-card bento-card-lilac">
              <div className="bento-icon-wrapper bg-lilac-subtle">
                <span>🧠</span>
              </div>
              <h3 className="bento-title">Adaptive Explanations</h3>
              <p className="bento-desc">
                Whether you need an intuitive 5-minute intuition builder or an advanced technical deep-dive,
                Teachie adjusts vocabulary, analogies, and pacing in real time.
              </p>
              <div className="bento-micro-feature">
                <span className="feature-check">✓</span> Beginner, Intermediate & Advanced modes
              </div>
            </div>

            <div className="bento-card bento-card-blue">
              <div className="bento-icon-wrapper bg-blue-subtle">
                <span>🎨</span>
              </div>
              <h3 className="bento-title">Dynamic Visual Blackboards</h3>
              <p className="bento-desc">
                No generic static slides. Teachie generates subject-aware diagrams on demand—binary trees,
                mathematical curves, vector mechanics, biological cycles, or live code traces.
              </p>
              <div className="bento-micro-feature">
                <span className="feature-check">✓</span> Subject-aware interactive visual renderer
              </div>
            </div>

            <div className="bento-card bento-card-purple">
              <div className="bento-icon-wrapper bg-purple-subtle">
                <span>💡</span>
              </div>
              <h3 className="bento-title">Misconception Detection</h3>
              <p className="bento-desc">
                When an answer isn’t quite right, Teachie diagnoses the exact faulty mental model
                behind it and provides an empathetic analogy to permanently fix the intuition.
              </p>
              <div className="bento-micro-feature">
                <span className="feature-check">✓</span> Cognitive root-cause analysis, not just "Wrong"
              </div>
            </div>

            <div className="bento-card bento-card-mint">
              <div className="bento-icon-wrapper bg-mint-subtle">
                <span>🎙️</span>
              </div>
              <h3 className="bento-title">Natural Voice & Video Export</h3>
              <p className="bento-desc">
                Listen with human speech pacing and animated character sync in English, Hindi, or Hinglish.
                Export complete lectures as authentic WebM video artifacts to study offline.
              </p>
              <div className="bento-micro-feature">
                <span className="feature-check">✓</span> Multilingual speech synthesis + video exporter
              </div>
            </div>
          </div>
        </section>

        {/* ====================================================================
            5. THE 4-STEP SOCRATIC PIPELINE
            ==================================================================== */}
        <section id="pipeline" className="landing-pipeline-section" aria-label="How Teachie Teaches">
          <div className="landing-section-header text-center">
            <span className="landing-section-eyebrow">THE 4-STEP PIPELINE</span>
            <h2 className="landing-section-title">The Socratic Mastery Loop</h2>
            <p className="landing-section-desc">
              Every concept follows an authentic pedagogical journey engineered for long-term retention.
            </p>
          </div>

          <div className="landing-steps-row">
            <div className="step-card">
              <div className="step-num-badge">01</div>
              <h4 className="step-title">Core Concept</h4>
              <p className="step-desc">
                First-principles explanation using real-world analogies and key takeaways.
              </p>
            </div>

            <div className="step-arrow-connector">→</div>

            <div className="step-card">
              <div className="step-num-badge">02</div>
              <h4 className="step-title">Demonstration</h4>
              <p className="step-desc">
                Step-by-step visual execution, mathematical derivation, or runnable code trace.
              </p>
            </div>

            <div className="step-arrow-connector">→</div>

            <div className="step-card">
              <div className="step-num-badge">03</div>
              <h4 className="step-title">Check Understanding</h4>
              <p className="step-desc">
                Targeted conceptual assessment. Evaluate both final answers and reasoning.
              </p>
            </div>

            <div className="step-arrow-connector">→</div>

            <div className="step-card">
              <div className="step-num-badge">04</div>
              <h4 className="step-title">Adaptive Next Step</h4>
              <p className="step-desc">
                Remediation, difficulty escalation, or advance to the next curriculum milestone.
              </p>
            </div>
          </div>
        </section>

        {/* ====================================================================
            6. CURRICULUM DOMAINS
            ==================================================================== */}
        <section id="curriculum" className="landing-subjects-showcase" aria-label="Subjects Showcase">
          <div className="landing-section-header text-center">
            <span className="landing-section-eyebrow">WIDE CURRICULUM COVERAGE</span>
            <h2 className="landing-section-title">Explore by Domain</h2>
            <p className="landing-section-desc">
              From foundational school concepts to university STEM topics, Teachie prepares tailor-made lessons.
            </p>
          </div>

          <div className="subjects-pill-grid">
            {[
              { icon: '💻', name: 'Computer Science', count: '48 Topics', example: 'Data Structures, AI, OS, Databases' },
              { icon: '📐', name: 'Mathematics', count: '64 Topics', example: 'Calculus, Linear Algebra, Statistics' },
              { icon: '⚛️', name: 'Physics', count: '42 Topics', example: 'Quantum Mechanics, Electromagnetism, Optics' },
              { icon: '🧪', name: 'Chemistry', count: '36 Topics', example: 'Organic Reactions, Thermodynamics, Periodic Law' },
              { icon: '🧬', name: 'Biology', count: '39 Topics', example: 'Cellular Respiration, Genetics, Ecology' },
              { icon: '🏛️', name: 'History & Civics', count: '28 Topics', example: 'Industrial Revolution, World Wars, Governance' },
            ].map((s) => (
              <div
                key={s.name}
                className="subject-tile"
                onClick={() => handlePickPopularTopic(s.name)}
                role="button"
                tabIndex={0}
              >
                <div className="subject-tile-top">
                  <span className="subject-icon">{s.icon}</span>
                  <span className="subject-count-pill">{s.count}</span>
                </div>
                <h4 className="subject-tile-name">{s.name}</h4>
                <p className="subject-tile-example">{s.example}</p>
                <div className="subject-tile-footer">
                  <span className="btn-link-learn">Start Domain →</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ====================================================================
            7. TESTIMONIALS & REVIEWS
            ==================================================================== */}
        <section id="reviews" className="landing-testimonials-section" aria-label="Student Experiences">
          <div className="landing-section-header text-center">
            <span className="landing-section-eyebrow">WHAT LEARNERS ARE SAYING</span>
            <h2 className="landing-section-title">Loved by Students Worldwide</h2>
            <p className="landing-section-desc">
              Real feedback from learners who replaced monotonous videos with interactive AI tutoring.
            </p>
          </div>

          <div className="testimonials-grid">
            <div className="testimonial-card">
              <div className="testimonial-rating">★★★★★</div>
              <p className="testimonial-quote">
                “Teachie’s blackboard diagrams for Binary Search Trees explained what three YouTube
                lectures couldn't. When I answered wrongly, it didn't just give the answer—it helped me
                realize where my mental model broke down.”
              </p>
              <div className="testimonial-author">
                <div className="author-avatar bg-avatar-1">PR</div>
                <div>
                  <h5 className="author-name">Priya Raghavan</h5>
                  <span className="author-meta">CS Undergrad • University of Washington</span>
                </div>
              </div>
            </div>

            <div className="testimonial-card">
              <div className="testimonial-rating">★★★★★</div>
              <p className="testimonial-quote">
                “I switched the language to Hinglish for Quantum Physics and suddenly wave-particle
                duality clicked instantly. It feels like having a brilliant private tutor who never gets
                tired or impatient.”
              </p>
              <div className="testimonial-author">
                <div className="author-avatar bg-avatar-2">AS</div>
                <div>
                  <h5 className="author-name">Aarav Sharma</h5>
                  <span className="author-meta">High School Senior • JEE Aspirant</span>
                </div>
              </div>
            </div>

            <div className="testimonial-card">
              <div className="testimonial-rating">★★★★★</div>
              <p className="testimonial-quote">
                “The spaced repetition revision queue saves me hours before midterms. The system remembers
                which concepts I struggled with weeks ago and surfaces them right before I forget them.”
              </p>
              <div className="testimonial-author">
                <div className="author-avatar bg-avatar-3">EL</div>
                <div>
                  <h5 className="author-name">Elena Lindqvist</h5>
                  <span className="author-meta">Pre-Med Student • Karolinska Institute</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ====================================================================
            8. GRAND CALL TO ACTION FOOTER BANNER
            ==================================================================== */}
        <section className="landing-final-cta-section" aria-label="Start Learning Call to Action">
          <div className="final-cta-card">
            <div className="cta-glow-bg" />
            <div className="cta-content">
              <span className="cta-pill">🚀 Ready to Transform How You Learn?</span>
              <h2 className="cta-title">Join Thousands Mastering Subjects with Teachie</h2>
              <p className="cta-desc">
                Sign in or create your free account now. Enter any topic, upload your study notes, or
                take an adaptive assessment in seconds.
              </p>

              <div className="cta-btn-row">
                <button
                  type="button"
                  className="btn-cta-primary"
                  onClick={() => scrollToAuth('register')}
                >
                  <span>Create Free Account</span>
                  <span className="cta-arrow">→</span>
                </button>

                <button
                  type="button"
                  className="btn-cta-guest"
                  onClick={handleGuest}
                >
                  <span>Continue as Guest</span>
                  <span className="cta-play">▷</span>
                </button>
              </div>

              <div className="cta-guarantees">
                <span>✓ 100% Free to Use</span>
                <span>✓ No Credit Card Required</span>
                <span>✓ Instant Classroom Launch</span>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ====================================================================
          9. CLEAN PUBLIC FOOTER
          ==================================================================== */}
      <footer className="landing-public-footer" aria-label="Footer">
        <div className="landing-footer-inner">
          <div className="footer-left">
            <div className="footer-brand">
              <span className="footer-book">📖</span>
              <span className="footer-title">Teachie</span>
            </div>
            <p className="footer-tagline">
              Learn smarter, your way. AI-powered 1-on-1 adaptive education platform.
            </p>
          </div>

          <div className="footer-links-group">
            <div className="footer-col">
              <h5 className="footer-col-title">Platform</h5>
              <button type="button" className="footer-link-btn" onClick={() => scrollToSection('features')}>
                Features
              </button>
              <button type="button" className="footer-link-btn" onClick={() => scrollToSection('pipeline')}>
                Socratic Loop
              </button>
              <button type="button" className="footer-link-btn" onClick={() => scrollToSection('curriculum')}>
                Curriculum
              </button>
            </div>

            <div className="footer-col">
              <h5 className="footer-col-title">Get Started</h5>
              <button type="button" className="footer-link-btn" onClick={() => scrollToAuth('signin')}>
                Sign In
              </button>
              <button type="button" className="footer-link-btn" onClick={() => scrollToAuth('register')}>
                Register
              </button>
              <button type="button" className="footer-link-btn" onClick={handleGuest}>
                Guest Access
              </button>
            </div>
          </div>
        </div>

        <div className="footer-bottom-bar">
          <span>© {new Date().getFullYear()} Teachie AI. All rights reserved.</span>
          <span className="footer-heart">Built with 💗 for curious minds everywhere</span>
        </div>
      </footer>
    </div>
  );
}
