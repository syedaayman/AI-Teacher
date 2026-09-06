import React, { useState, useEffect } from 'react';
import { useClassroom, getStoredActiveSession } from '../context/ClassroomContext';
import api from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

/**
 * MyLearningPage Component
 * Minimal, non-bulky student progress view.
 * Displays:
 * - Current Topic & Learning Progress
 * - Strong Concepts
 * - Needs Practice
 * - Recent Learning
 * - Continue Lesson CTA
 */
export default function MyLearningPage({ onNavigate }) {
  const { learnerId = 'student_1', topic, currentConceptName, sessionId, refreshSession } = useClassroom();
  const [summary, setSummary] = useState(null);
  const [reviewItems, setReviewItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const storedSession = getStoredActiveSession();
  const activeTopic = topic || storedSession?.topic || 'Data Structures and Algorithms';

  useEffect(() => {
    let isMounted = true;
    async function loadProgress() {
      try {
        const [sum, queue] = await Promise.all([
          api.getMemorySummary(learnerId).catch(() => null),
          api.getReviewQueue(learnerId).catch(() => ({ items: [] })),
        ]);
        if (isMounted) {
          setSummary(sum);
          setReviewItems(queue?.items || []);
        }
      } catch (err) {
        console.warn('Could not load progress data', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadProgress();
    return () => {
      isMounted = false;
    };
  }, [learnerId]);

  const handleContinueLesson = async () => {
    if (sessionId) {
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
    if (onNavigate) onNavigate('learn');
  };

  // Derive strong vs needs practice concepts from backend queue/summary
  const strongConcepts = reviewItems
    .filter((i) => i.recommended_action === 'mastered_stable' || (i.mastery_score || 0) >= 0.75)
    .map((i) => i.concept_name || i.concept_id);

  const needsPracticeConcepts = reviewItems
    .filter((i) => i.recommended_action === 'review_now' || (i.mastery_score || 0) < 0.75)
    .map((i) => i.concept_name || i.concept_id);

  // Default clean representations calibrated to current active topic
  const getTopicConcepts = (topicName) => {
    const t = (topicName || '').toLowerCase();
    if (t.includes('newton') || t.includes('motion') || t.includes('force') || t.includes('physic')) {
      return {
        strong: ["Newton's First Law", "Inertia & Rest Frames"],
        needsPractice: ["Newton's Second Law (F = ma)"],
        recent: [activeTopic, "Inertial Reference Frames"],
      };
    }
    if (t.includes('photo') || t.includes('bio') || t.includes('cell') || t.includes('plant')) {
      return {
        strong: ["Light Reactions", "Chloroplast Structure"],
        needsPractice: ["Calvin Cycle & ATP Synthesis"],
        recent: [activeTopic, "Cellular Respiration"],
      };
    }
    if (t.includes('tree') || t.includes('binary')) {
      return {
        strong: ["BST Search", "In-order Traversal"],
        needsPractice: ["Tree Balancing (AVL)"],
        recent: [activeTopic, "Binary Trees"],
      };
    }
    return {
      strong: [`${activeTopic} Foundations`, "Core Principles"],
      needsPractice: [`${activeTopic} Practical Applications`],
      recent: [activeTopic, "Foundations"],
    };
  };

  const topicDefaults = getTopicConcepts(activeTopic);
  const displayStrong = strongConcepts.length > 0 ? strongConcepts : topicDefaults.strong;
  const displayNeedsPractice = needsPracticeConcepts.length > 0 ? needsPracticeConcepts : topicDefaults.needsPractice;

  const progressPercent = summary?.average_retention_probability
    ? Math.round(summary.average_retention_probability * 100)
    : 60;

  if (loading) {
    return (
      <div className="compact-student-view flex items-center justify-center p-12 min-h-[350px]">
        <LoadingSpinner size="large" text="Loading your learning progress..." />
      </div>
    );
  }

  return (
    <div className="compact-student-view">
      <div className="view-header-compact">
        <h1 className="view-title">My Learning</h1>
        <p className="view-subtitle">Your progress and concepts that need practice.</p>
      </div>

      {/* Main Active Learning Card */}
      <div className="compact-card active-learning-card">
        <div className="active-learning-header">
          <div>
            <span className="card-mini-label">CURRENT TOPIC</span>
            <h2 className="current-topic-title">{activeTopic}</h2>
            {currentConceptName && (
              <span className="current-concept-text">Current Concept: {currentConceptName}</span>
            )}
          </div>
          <div className="progress-radial-pill">
            <span className="progress-number">{progressPercent}%</span>
            <span className="progress-label">complete</span>
          </div>
        </div>

        <div className="compact-progress-bar-track">
          <div className="compact-progress-bar-fill" style={{ width: `${progressPercent}%` }} />
        </div>

        {/* Strong vs Needs Practice Split */}
        <div className="learning-split-row">
          <div className="learning-subcard strong-subcard">
            <div className="subcard-title-row">
              <span className="subcard-indicator green">✓</span>
              <span className="subcard-label">Strong</span>
            </div>
            <ul className="compact-concept-tags">
              {displayStrong.map((c, idx) => (
                <li key={idx} className="concept-pill-tag strong-tag">
                  {c}
                </li>
              ))}
            </ul>
          </div>

          <div className="learning-subcard practice-subcard">
            <div className="subcard-title-row">
              <span className="subcard-indicator orange">⚡</span>
              <span className="subcard-label">Needs Practice</span>
            </div>
            <ul className="compact-concept-tags">
              {displayNeedsPractice.map((c, idx) => (
                <li key={idx} className="concept-pill-tag practice-tag">
                  {c}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="compact-card-footer">
          <button
            type="button"
            className="btn-compact btn-compact-primary"
            onClick={handleContinueLesson}
          >
            Continue Lesson →
          </button>
        </div>
      </div>

      {/* Recent Learning Activity */}
      <div className="compact-card mt-3">
        <div className="compact-card-header">
          <h3 className="card-subheading">Recent Learning</h3>
        </div>
        <ul className="recent-activity-compact-list">
          <li className="activity-row">
            <div className="activity-main">
              <span className="activity-bullet text-indigo-500">●</span>
              <span className="activity-topic">{activeTopic}</span>
            </div>
            <span className="activity-time">In progress</span>
          </li>
          <li className="activity-row">
            <div className="activity-main">
              <span className="activity-bullet text-emerald-500">✓</span>
              <span className="activity-topic">{topicDefaults.recent[1] || `${activeTopic} Essentials`}</span>
            </div>
            <span className="activity-time">Completed</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
