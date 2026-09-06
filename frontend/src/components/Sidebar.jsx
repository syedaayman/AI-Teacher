import React from 'react';
import { useClassroom } from '../context/ClassroomContext';

/**
 * Sidebar Component
 * Perfectly matches the reference design:
 * - Brand: AI Teacher ("Learn smarter, your way") with purple book icon
 * - Navigation: Home, Learn, My Learning, Assessments, Revision
 * - Active item: Soft lilac pill background with deep purple icon/text
 * - Bottom illustration: Potted plant with "Small Steps Big Progress 💗"
 */
const STUDENT_NAV_ITEMS = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'my-learning', label: 'My Learning', icon: '📊' },
  { id: 'learn', label: 'Start Learning', icon: '🎓' },
  { id: 'assessments', label: 'Assessments', icon: '📝' },
  { id: 'revision', label: 'Revision', icon: '🔄' },
];

export default function Sidebar({ activeTab, onSelectTab, onSignOut }) {
  const { sessionId, status } = useClassroom();
  const hasActiveSession = Boolean(sessionId && status === 'active');

  return (
    <aside className="production-sidebar" aria-label="Main Navigation">
      {/* 1. Brand Logo */}
      <div
        className="sidebar-brand-box"
        onClick={() => onSelectTab('home')}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onSelectTab('home');
        }}
      >
        <div className="brand-book-icon" aria-hidden="true">
          <span>📖</span>
        </div>
        <div className="brand-titles">
          <span className="brand-main-title">AI Teacher</span>
          <span className="brand-sub-title">Learn smarter, your way</span>
        </div>
      </div>

      {/* 2. Navigation Items */}
      <nav className="sidebar-nav-container">
        <ul className="sidebar-nav-list">
          {STUDENT_NAV_ITEMS.map((item) => {
            const isActive =
              activeTab === item.id ||
              (item.id === 'learn' && (activeTab === 'setup' || activeTab === 'study-materials'));

            return (
              <li key={item.id} className="nav-list-item">
                <button
                  type="button"
                  className={`nav-item-btn ${isActive ? 'active' : ''}`}
                  onClick={() => onSelectTab(item.id)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </button>
              </li>
            );
          })}

          {/* Active Classroom indicator if class is live */}
          {hasActiveSession && (
            <li className="nav-list-item live-class-item">
              <button
                type="button"
                className={`nav-item-btn live-btn ${activeTab === 'classroom' ? 'active' : ''}`}
                onClick={() => onSelectTab('classroom')}
              >
                <span className="nav-icon">🏫</span>
                <span className="nav-label">Live Classroom</span>
                <span className="live-pulsar-dot" />
              </button>
            </li>
          )}
        </ul>
      </nav>

      {/* 3. Bottom Plant Decoration ("Small Steps Big Progress 💗") */}
      <div className="sidebar-bottom-plant-card">
        <div className="plant-image-wrapper">
          <img
            src="/images/potted_plant.jpg"
            alt="Small plant decoration"
            className="sidebar-plant-img"
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
        </div>
        <p className="sidebar-plant-caption">
          Small<br />
          Steps<br />
          Big Progress 💗
        </p>
      </div>

      {/* 4. Exit / Sign Out Button */}
      <div className="sidebar-auth-exit">
        <button
          type="button"
          className="sidebar-signout-btn"
          onClick={() => {
            if (onSignOut) onSignOut();
            else onSelectTab('landing');
          }}
          title="Sign out and return to landing page"
        >
          <span className="signout-icon">🚪</span>
          <span className="signout-text">Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
