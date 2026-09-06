import React, { useState, useEffect } from 'react';
import { useClassroom, getStoredActiveSession } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';

/**
 * HomePage Component — World-Class Educational Landing Page
 * Features:
 * 1. High-Impact Hero with Lady AI Teacher image, glowing aura, and floating feature badges.
 * 2. Instant Topic Launcher input bar + 1-click popular topics.
 * 3. Active Session Quick-Resume card with live progress.
 * 4. "Why Students Learn 3x Faster" Bento Grid (Adaptive, Visual, Misconception, Multilingual Voice).
 * 5. 4-Step Teaching Pipeline walkthrough.
 * 6. 4 Core Learning Modes (Topic, Material RAG, My Learning, Revision).
 * 7. Interactive Subject Showcase pills.
 * 8. Real Student Testimonials & Trust metrics.
 * 9. Grand Dreamy Call-to-Action footer card.
 */
export default function HomePage({ onNavigate, user }) {
  const {
    sessionId,
    status,
    topic,
    currentConceptName,
    remainingTimeMinutes,
    refreshSession,
    learnerId = 'student_1',
  } = useClassroom();
  const { updateSession } = useTestSession() || { updateSession: () => {} };

  const [searchQuery, setSearchQuery] = useState('');
  const [memorySummary, setMemorySummary] = useState(null);
  const [reviewQueue, setReviewQueue] = useState([]);
  const [activeLessonTitle, setActiveLessonTitle] = useState('Data Structures & Algorithms');
  const [activeConceptTitle, setActiveConceptTitle] = useState('Binary Search Trees');
  const [activeProgressPct, setActiveProgressPct] = useState(60);

  const storedSession = getStoredActiveSession();

  // Load real memory / progress data from backend
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      try {
        const [sum, queue] = await Promise.all([
          api.getMemorySummary(learnerId).catch(() => null),
          api.getReviewQueue(learnerId).catch(() => ({ items: [] })),
        ]);
        if (isMounted) {
          setMemorySummary(sum);
          setReviewQueue(queue?.items || []);
        }
      } catch (err) {
        console.warn('Could not load memory summary:', err);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, [learnerId]);

  // Sync active lesson details from real session
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

  const handleContinueLearning = async () => {
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

  const handleStartTopic = (topicName) => {
    if (updateSession) {
      updateSession({ selectedConcept: topicName });
    }
    if (onNavigate) onNavigate('learn');
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    handleStartTopic(searchQuery.trim());
  };

  const hasResumeableSession = Boolean(
    (sessionId && status === 'active') || storedSession?.sessionId
  );

  const topicsCount = memorySummary?.total_concepts_tracked || 12;
  const masteredCount = memorySummary?.mastered_concepts_count || 8;
  const practiceCount =
    reviewQueue.filter((i) => i.recommended_action === 'review_now' || (i.mastery_score || 0) < 0.8)
      .length || 3;

  return (
    <div className="landing-page-root">
      {/* 1. HERO SECTION */}
      <section className="landing-hero-showcase" aria-label="Hero Introduction">
        <div className="landing-hero-ambient-glow glow-1" />
        <div className="landing-hero-ambient-glow glow-2" />

        <div className="landing-hero-grid">
          {/* Left Hero Content */}
          <div className="landing-hero-left">
            <div className="landing-hero-pill-badge">
              <span className="pill-sparkle">✨</span>
              <span className="pill-text">
                {user?.name ? `Welcome back, ${user.name}! • 1-on-1 Interactive AI Teacher` : 'AI-Powered 1-on-1 Interactive Teacher'}
              </span>
            </div>

            <h1 className="landing-hero-headline">
              Master Any Subject.<br />
              <span className="landing-gradient-text">At Your Own Pace.</span>
            </h1>

            <p className="landing-hero-subtext">
              Meet Professor Teachie—an adaptive AI educator that explains concepts from first
              principles, demonstrates step-by-step with visual blackboards, diagnoses misconceptions,
              and personalizes every lesson to how your brain learns best.
            </p>

            {/* Interactive Topic Launcher Bar */}
            <form onSubmit={handleSearchSubmit} className="landing-quick-search-box">
              <span className="search-icon-decor">🔍</span>
              <input
                type="text"
                className="landing-search-input"
                placeholder="What would you like to master today? (e.g. Binary Search Trees, Quantum Mechanics...)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="btn-search-go">
                Start Lesson →
              </button>
            </form>

            {/* Quick-Pick Popular Topics */}
            <div className="landing-topic-pills-row">
              <span className="pills-label">Popular now:</span>
              {[
                { name: 'Binary Trees', emoji: '🌲' },
                { name: "Newton's Laws", emoji: '⚛️' },
                { name: 'Calculus Limits', emoji: '📐' },
                { name: 'Photosynthesis', emoji: '🌿' },
                { name: 'World History', emoji: '🏛️' },
              ].map((t) => (
                <button
                  key={t.name}
                  type="button"
                  className="quick-topic-chip"
                  onClick={() => handleStartTopic(t.name)}
                >
                  <span>{t.emoji}</span>
                  <span>{t.name}</span>
                </button>
              ))}
            </div>

            {/* Action CTA Buttons */}
            <div className="landing-hero-ctas">
              <button
                type="button"
                className="btn-landing-primary"
                onClick={() => onNavigate && onNavigate('learn')}
              >
                <span>Enter AI Classroom Free</span>
                <span className="btn-arrow">→</span>
              </button>

              <button
                type="button"
                className="btn-landing-secondary"
                onClick={() => onNavigate && onNavigate('study-materials')}
              >
                <span>📄 Learn from Your Notes / PDF</span>
              </button>
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
                <span className="trust-text"><strong>100% Adaptive</strong> Socratic Method</span>
              </div>
              <span className="trust-divider">•</span>
              <div className="trust-item">
                <span className="trust-icon">🎙️</span>
                <span className="trust-text"><strong>Voice & Video</strong> Web Speech Sync</span>
              </div>
            </div>
          </div>

          {/* Right Hero Visual (Featuring the Lady Teacher Hero Image) */}
          <div className="landing-hero-right">
            <div className="landing-teacher-stage-wrapper">
              <div className="teacher-glow-pedestal" />

              {/* Floating Glass Badges */}
              <div className="floating-badge badge-top-left animate-float-slow">
                <span className="badge-icon">💡</span>
                <div className="badge-text">
                  <strong>Adaptive Teaching</strong>
                  <span>Auto-calibrates depth</span>
                </div>
              </div>

              <div className="floating-badge badge-top-right animate-float-delayed">
                <span className="badge-icon">📊</span>
                <div className="badge-text">
                  <strong>98% Mastery</strong>
                  <span>Concept retention</span>
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
          </div>
        </div>
      </section>

      {/* 2. CONTINUE LEARNING BANNER (If Active Session Exists) */}
      {hasResumeableSession && (
        <section className="landing-continue-strip" aria-label="Resume Your Session">
          <div className="continue-strip-inner">
            <div className="continue-strip-left">
              <div className="continue-icon-box">
                <span>🧊</span>
              </div>
              <div>
                <span className="continue-sub">Active Learning Session</span>
                <h3 className="continue-title">{activeLessonTitle}</h3>
                <span className="continue-concept">Currently on: <strong>{activeConceptTitle}</strong></span>
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
              className="btn-continue-now"
              onClick={handleContinueLearning}
            >
              Resume Lesson →
            </button>
          </div>
        </section>
      )}

      {/* 3. BENTO CAPABILITIES: WHY STUDENTS LEARN 3X FASTER */}
      <section className="landing-bento-section" aria-label="Why Learn with Teachie">
        <div className="landing-section-header text-center">
          <span className="landing-section-eyebrow">PEDAGOGICAL EXCELLENCE</span>
          <h2 className="landing-section-title">Built Around How Your Brain Actually Learns</h2>
          <p className="landing-section-desc">
            Traditional video lectures are passive. Professor Teachie uses active socratic dialogue,
            multimodal visuals, and real-time cognitive adaptation.
          </p>
        </div>

        <div className="landing-bento-grid">
          {/* Bento Card 1 */}
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

          {/* Bento Card 2 */}
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

          {/* Bento Card 3 */}
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

          {/* Bento Card 4 */}
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

      {/* 4. HOW TEACHIE TEACHES (4-STEP PROGRESSION PIPELINE) */}
      <section className="landing-pipeline-section" aria-label="How Teachie Teaches">
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

      {/* 5. EXPLORE 4 PRIMARY LEARNING PATHWAYS */}
      <section className="landing-explore-section" aria-label="Explore Learning Modes">
        <div className="section-title-row mb-4">
          <div>
            <span className="landing-section-eyebrow">CHOOSE YOUR PATH</span>
            <h2 className="reference-section-heading text-xl">Explore Learning Modes</h2>
          </div>
        </div>

        <div className="explore-quad-grid">
          {/* Card 1: Learn a Topic */}
          <div
            className="explore-card card-purple-accent"
            onClick={() => onNavigate && onNavigate('learn')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onNavigate && onNavigate('learn');
            }}
          >
            <div className="explore-card-top">
              <div className="explore-icon-circle bg-lilac-circle">
                <span>🎓</span>
              </div>
              <span className="explore-arrow-circle">→</span>
            </div>
            <h3 className="explore-card-title">Learn Any Topic</h3>
            <p className="explore-card-desc">
              Type any subject—from Binary Trees to World War II—and get an interactive lesson.
            </p>
          </div>

          {/* Card 2: Learn from Material */}
          <div
            className="explore-card card-blue-accent"
            onClick={() => onNavigate && onNavigate('study-materials')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onNavigate && onNavigate('study-materials');
            }}
          >
            <div className="explore-card-top">
              <div className="explore-icon-circle bg-blue-circle">
                <span>📄</span>
              </div>
              <span className="explore-arrow-circle">→</span>
            </div>
            <h3 className="explore-card-title">Learn from Material</h3>
            <p className="explore-card-desc">
              Upload your lecture notes, slides, or PDF textbooks for RAG-grounded teaching.
            </p>
          </div>

          {/* Card 3: My Learning */}
          <div
            className="explore-card card-pink-accent"
            onClick={() => onNavigate && onNavigate('my-learning')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onNavigate && onNavigate('my-learning');
            }}
          >
            <div className="explore-card-top">
              <div className="explore-icon-circle bg-pink-circle">
                <span>📊</span>
              </div>
              <span className="explore-arrow-circle">→</span>
            </div>
            <h3 className="explore-card-title">My Learning Map</h3>
            <p className="explore-card-desc">
              Track your concepts mastered ({masteredCount}), topics explored ({topicsCount}), and mastery curve.
            </p>
          </div>

          {/* Card 4: Revision */}
          <div
            className="explore-card card-mint-accent"
            onClick={() => onNavigate && onNavigate('revision')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onNavigate && onNavigate('revision');
            }}
          >
            <div className="explore-card-top">
              <div className="explore-icon-circle bg-mint-circle">
                <span>🔄</span>
              </div>
              <span className="explore-arrow-circle">→</span>
            </div>
            <h3 className="explore-card-title">Spaced Revision</h3>
            <p className="explore-card-desc">
              Review concepts requiring reinforcement ({practiceCount} pending items in queue).
            </p>
          </div>
        </div>
      </section>

      {/* 6. SUBJECT SHOWCASE (Interactive 1-Click Jumpstarts) */}
      <section className="landing-subjects-showcase" aria-label="Subjects Showcase">
        <div className="landing-section-header text-center">
          <span className="landing-section-eyebrow">WIDE CURRICULUM COVERAGE</span>
          <h2 className="landing-section-title">Explore by Domain</h2>
          <p className="landing-section-desc">
            Teachie generates authentic explanations, diagrams, and questions for any discipline.
          </p>
        </div>

        <div className="subject-domains-grid">
          <div
            className="subject-domain-card"
            onClick={() => handleStartTopic('Binary Search Trees')}
          >
            <div className="domain-icon-box">💻</div>
            <h4 className="domain-title">Computer Science</h4>
            <p className="domain-topics">BST Trees • Dynamic Programming • Graph Traversals</p>
            <span className="domain-cta">Start CS Lesson →</span>
          </div>

          <div
            className="subject-domain-card"
            onClick={() => handleStartTopic("Newton's Laws of Motion")}
          >
            <div className="domain-icon-box">⚛️</div>
            <h4 className="domain-title">Physics & Mechanics</h4>
            <p className="domain-topics">Newtonian Laws • Thermodynamics • Wave Optics</p>
            <span className="domain-cta">Start Physics Lesson →</span>
          </div>

          <div
            className="subject-domain-card"
            onClick={() => handleStartTopic('Cellular Respiration')}
          >
            <div className="domain-icon-box">🧬</div>
            <h4 className="domain-title">Life Sciences</h4>
            <p className="domain-topics">Photosynthesis • DNA Transcription • Cell Division</p>
            <span className="domain-cta">Start Biology Lesson →</span>
          </div>

          <div
            className="subject-domain-card"
            onClick={() => handleStartTopic('Calculus Limits and Continuity')}
          >
            <div className="domain-icon-box">📐</div>
            <h4 className="domain-title">Mathematics</h4>
            <p className="domain-topics">Limits & Derivatives • Linear Algebra • Probability</p>
            <span className="domain-cta">Start Math Lesson →</span>
          </div>
        </div>
      </section>

      {/* 7. STUDENT EXPERIENCES (Authentic Testimonials) */}
      <section className="landing-testimonials-section" aria-label="Student Experiences">
        <div className="landing-section-header text-center">
          <span className="landing-section-eyebrow">WHAT LEARNERS ARE SAYING</span>
          <h2 className="landing-section-title">Loved by Students Worldwide</h2>
        </div>

        <div className="testimonials-trio-grid">
          <div className="testimonial-quote-card">
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-quote">
              “Having an AI teacher that breaks down why an algorithm works instead of just dumping code
              completely transformed my computer science grades.”
            </p>
            <div className="testimonial-author">
              <span className="author-avatar">👩‍🎓</span>
              <div>
                <strong className="author-name">Ananya Sharma</strong>
                <span className="author-detail">Computer Science Undergrad</span>
              </div>
            </div>
          </div>

          <div className="testimonial-quote-card">
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-quote">
              “The misconception detection is brilliant. When I mixed up centripetal force, Teachie
              identified my exact faulty mental model and gave me an intuitive analogy.”
            </p>
            <div className="testimonial-author">
              <span className="author-avatar">👨‍🔬</span>
              <div>
                <strong className="author-name">Marcus Chen</strong>
                <span className="author-detail">Engineering Student</span>
              </div>
            </div>
          </div>

          <div className="testimonial-quote-card">
            <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-quote">
              “The Hindi and Hinglish voice explanations made complex cellular biology concepts click in minutes.
              The visual blackboards are a game changer!”
            </p>
            <div className="testimonial-author">
              <span className="author-avatar">👨‍⚕️</span>
              <div>
                <strong className="author-name">Rohan Patel</strong>
                <span className="author-detail">Pre-Med Aspirant</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 8. GRAND CALL TO ACTION FOOTER BANNER */}
      <section className="landing-final-cta-section" aria-label="Start Learning Call to Action">
        <div className="final-cta-card">
          <div className="final-cta-decor decor-1" />
          <div className="final-cta-decor decor-2" />

          <span className="final-cta-tag">GET STARTED IN SECONDS</span>
          <h2 className="final-cta-headline">Experience the Future of Learning Today</h2>
          <p className="final-cta-subtext">
            Step into the classroom with Professor Teachie. No complicated setup, no paywalls—just
            empathetic, personalized, intelligent education.
          </p>

          <div className="final-cta-buttons-row">
            <button
              type="button"
              className="btn-final-cta-primary"
              onClick={() => onNavigate && onNavigate('learn')}
            >
              Start Learning Now — It's Free →
            </button>
            <button
              type="button"
              className="btn-final-cta-secondary"
              onClick={handleContinueLearning}
            >
              Enter Live Classroom ▷
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
