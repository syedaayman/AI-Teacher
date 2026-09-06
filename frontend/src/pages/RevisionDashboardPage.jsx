import React, { useState, useEffect } from 'react';
import { useClassroom } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';

/**
 * RevisionDashboardPage Component
 * Clean, minimal student revision view:
 * Heading: "Topics to Review"
 * Shows list of concepts with status (Needs Practice, Review Soon, Strong)
 * Action: "Review Now →" which starts a revision lesson.
 * No technical IDs or SM-2 decay jargon.
 */
export default function RevisionDashboardPage({ onNavigate }) {
  const { learnerId = 'student_1' } = useClassroom();
  const { updateSession } = useTestSession() || { updateSession: () => {} };
  const [reviewQueue, setReviewQueue] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadRevision() {
      try {
        const data = await api.getReviewQueue(learnerId).catch(() => ({ items: [] }));
        if (isMounted) {
          setReviewQueue(data?.items || []);
        }
      } catch (err) {
        console.warn('Could not load review items', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadRevision();
    return () => {
      isMounted = false;
    };
  }, [learnerId]);

  const handleReviewConcept = (conceptName) => {
    if (updateSession) {
      updateSession({ selectedConcept: conceptName });
    }
    if (typeof onNavigate === 'function') {
      onNavigate('learn');
    }
  };

  const { topic } = useClassroom();
  const activeTopic = topic || 'Newton\'s Laws of Motion';

  // Map backend items to student-friendly format or provide topic-calibrated defaults
  const getTopicRevisionItems = () => {
    const t = activeTopic.toLowerCase();
    if (t.includes('newton') || t.includes('motion') || t.includes('force') || t.includes('physic')) {
      return [
        { title: "Newton's Second Law (F = ma)", status: 'Needs Practice', type: 'high' },
        { title: 'Inertia & Reference Frames', status: 'Review Soon', type: 'medium' },
        { title: "Newton's Third Law (Action-Reaction)", status: 'Strong', type: 'low' },
      ];
    }
    if (t.includes('photo') || t.includes('bio') || t.includes('cell')) {
      return [
        { title: 'Calvin Cycle & ATP Synthesis', status: 'Needs Practice', type: 'high' },
        { title: 'Light Dependent Reactions', status: 'Review Soon', type: 'medium' },
        { title: 'Chloroplast & Thylakoids', status: 'Strong', type: 'low' },
      ];
    }
    return [
      { title: `${activeTopic} Core Mechanics`, status: 'Needs Practice', type: 'high' },
      { title: `${activeTopic} Principles`, status: 'Review Soon', type: 'medium' },
      { title: `${activeTopic} Fundamentals`, status: 'Strong', type: 'low' },
    ];
  };

  const items = reviewQueue.length > 0
    ? reviewQueue.map((item) => {
        let statusText = 'Review Soon';
        let statusType = 'medium';
        if (item.recommended_action === 'review_now' || (item.mastery_score || 0) < 0.6) {
          statusText = 'Needs Practice';
          statusType = 'high';
        } else if (item.recommended_action === 'mastered_stable' || (item.mastery_score || 0) >= 0.8) {
          statusText = 'Strong';
          statusType = 'low';
        }
        return {
          title: item.concept_name || item.concept_id || 'Core Concept',
          status: statusText,
          type: statusType,
        };
      })
    : getTopicRevisionItems();

  return (
    <div className="compact-student-view">
      <div className="view-header-compact">
        <h1 className="view-title">Topics to Review</h1>
        <p className="view-subtitle">Review concepts that need attention to keep your understanding fresh.</p>
      </div>

      <div className="compact-card">
        {loading ? (
          <div className="compact-loading-state">
            <div className="compact-spinner" />
            <p className="loading-headline">Checking your revision topics...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="compact-empty-state">
            <span className="empty-icon">✨</span>
            <p className="empty-title">You're all caught up!</p>
            <span className="empty-sub">No concepts need review right now. Ready to learn something new?</span>
            <button
              type="button"
              className="btn-compact btn-compact-primary mt-2"
              onClick={() => onNavigate && onNavigate('learn')}
            >
              Start Learning →
            </button>
          </div>
        ) : (
          <div className="revision-items-compact-list">
            {items.map((item, idx) => (
              <div key={idx} className="revision-compact-row">
                <div className="revision-row-info">
                  <span className="revision-topic-name">{item.title}</span>
                  <span className={`revision-status-badge badge-${item.type}`}>
                    {item.status}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn-compact btn-compact-secondary btn-review-action"
                  onClick={() => handleReviewConcept(item.title)}
                >
                  Review Now →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
