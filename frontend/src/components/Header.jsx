import React, { useState } from 'react';
import { useClassroom } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';

/**
 * Top Navigation Header Bar
 * Exactly matches the design reference:
 * - Search bar: "Search for any topic, concept or your materials..."
 * - Language switcher: 🌐 English ▾ (English / Hindi / Hinglish)
 * - Notification bell 🔔
 * - Student Profile avatar + "Hi, Student ▾"
 */
export default function Header({ onNavigate, onSignOut, user }) {
  const { language = 'english', switchLanguage } = useClassroom();
  const { updateSession } = useTestSession() || { updateSession: () => {} };
  const [searchQuery, setSearchQuery] = useState('');
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    if (updateSession) {
      updateSession({ selectedConcept: searchQuery.trim() });
    }
    if (typeof onNavigate === 'function') {
      onNavigate('learn');
    }
  };

  const handleSelectLanguage = (newLang) => {
    if (typeof switchLanguage === 'function') {
      switchLanguage(newLang);
    }
    setShowLangMenu(false);
  };

  const displayName = user?.name || 'Student';
  const displayEmail = user?.email || 'student@teachie.ai';
  const displayRole = user?.isGuest ? 'Guest Learner' : user?.grade || 'Enrolled Student';
  const displayLang = language === 'hindi' ? 'Hindi' : language === 'hinglish' ? 'Hinglish' : 'English';

  return (
    <header className="production-top-header" aria-label="Main Header">
      {/* 1. Global Search Bar */}
      <form onSubmit={handleSearchSubmit} className="header-search-form">
        <span className="search-icon" aria-hidden="true">🔍</span>
        <input
          type="search"
          className="header-search-input"
          placeholder="Search for any topic, concept or your materials..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          aria-label="Search topics and materials"
        />
      </form>

      {/* 2. Right Controls */}
      <div className="header-right-group">
        {/* Language Selector Dropdown */}
        <div className="header-lang-dropdown-wrapper">
          <button
            type="button"
            className="header-pill-btn lang-pill"
            onClick={() => {
              setShowLangMenu(!showLangMenu);
              setShowProfileMenu(false);
            }}
            aria-label="Change language"
          >
            <span className="lang-icon">🌐</span>
            <span className="lang-name">{displayLang}</span>
            <span className="dropdown-arrow">▾</span>
          </button>

          {showLangMenu && (
            <div className="lang-menu-popover">
              <button
                type="button"
                className={`lang-option ${language === 'english' ? 'active' : ''}`}
                onClick={() => handleSelectLanguage('english')}
              >
                English
              </button>
              <button
                type="button"
                className={`lang-option ${language === 'hindi' ? 'active' : ''}`}
                onClick={() => handleSelectLanguage('hindi')}
              >
                हिंदी (Hindi)
              </button>
              <button
                type="button"
                className={`lang-option ${language === 'hinglish' ? 'active' : ''}`}
                onClick={() => handleSelectLanguage('hinglish')}
              >
                Hinglish
              </button>
            </div>
          )}
        </div>

        {/* Notification Bell */}
        <button type="button" className="header-icon-btn" aria-label="Notifications" title="No new notifications">
          <span className="bell-icon">🔔</span>
        </button>

        {/* Student Profile with Popover Menu */}
        <div className="header-profile-menu-container">
          <div
            className="header-profile-pill"
            onClick={() => {
              setShowProfileMenu(!showProfileMenu);
              setShowLangMenu(false);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                setShowProfileMenu(!showProfileMenu);
              }
            }}
            aria-label="User Profile Menu"
          >
            <div className="profile-avatar-circle">
              <span>👩‍🎓</span>
            </div>
            <span className="profile-greeting">Hi, {displayName}</span>
            <span className="dropdown-arrow">▾</span>
          </div>

          {showProfileMenu && (
            <div className="header-profile-popover" role="menu">
              <div className="popover-user-info">
                <div className="popover-avatar">
                  <span>👩‍🎓</span>
                </div>
                <div className="popover-details">
                  <span className="popover-name">{displayName}</span>
                  <span className="popover-role">{displayRole}</span>
                </div>
              </div>

              <div className="popover-menu-list">
                <button
                  type="button"
                  className="popover-menu-item"
                  onClick={() => {
                    setShowProfileMenu(false);
                    if (onNavigate) onNavigate('home');
                  }}
                >
                  <span>🏠</span>
                  <span>Home / Welcome Dashboard</span>
                </button>

                <button
                  type="button"
                  className="popover-menu-item"
                  onClick={() => {
                    setShowProfileMenu(false);
                    if (onNavigate) onNavigate('my-learning');
                  }}
                >
                  <span>📊</span>
                  <span>My Learning Dashboard</span>
                </button>

                <button
                  type="button"
                  className="popover-menu-item"
                  onClick={() => {
                    setShowProfileMenu(false);
                    if (onNavigate) onNavigate('learn');
                  }}
                >
                  <span>🎓</span>
                  <span>Start New Lesson</span>
                </button>

                <button
                  type="button"
                  className="popover-menu-item"
                  onClick={() => {
                    setShowProfileMenu(false);
                    if (onNavigate) onNavigate('landing');
                  }}
                >
                  <span>🏠</span>
                  <span>View Landing Page</span>
                </button>

                <button
                  type="button"
                  className="popover-menu-item signout-item"
                  onClick={() => {
                    setShowProfileMenu(false);
                    if (onSignOut) {
                      onSignOut();
                    } else if (onNavigate) {
                      onNavigate('landing');
                    }
                  }}
                >
                  <span>🚪</span>
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
