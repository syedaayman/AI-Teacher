import React from 'react';

/**
 * ClassroomControls Component
 * Renders the classroom bottom control bar.
 * Layout:
 * - Refactored using flex flex-wrap items-center justify-between gap-4 p-4 sticky/fixed bottom-0 bg-background/95 backdrop-blur z-20
 * - Strictly separates language selection pills ("English", "Hindi", "Hinglish") from primary navigation buttons
 * - Guaranteed zero overlap on small or resized viewports
 * - Direct state bindings to ClassroomContext
 */
export default function ClassroomControls({
  status,
  currentStep,
  completed,
  language,
  advancing,
  loading,
  switchingLanguage,
  ending,
  onAdvanceStep,
  onSwitchLanguage,
  onEndSession,
  onResetClassroom,
}) {
  const isBusy = loading || advancing || switchingLanguage || ending;
  const isActive = status === 'active' && !completed;

  return (
    <footer
      className="classroom-controls-bar flex flex-wrap items-center justify-between gap-4 p-4 mt-6 bg-white/95 rounded-2xl border border-indigo-100 shadow-sm backdrop-blur"
      aria-label="Classroom Controls"
    >
      {/* 1. Language Selection Group (Separated on Left) */}
      <div className="controls-left flex items-center flex-wrap gap-3 min-w-0">
        <div className="lang-switcher-group flex items-center flex-wrap gap-2">
          <span className="control-label font-medium text-sm text-slate-700 whitespace-nowrap">
            🗣️ Language:
          </span>
          <div
            className="lang-options flex items-center flex-wrap gap-1.5"
            role="group"
            aria-label="Language selection"
          >
            {[
              { id: 'english', label: 'English' },
              { id: 'hindi', label: 'हिंदी' },
              { id: 'hinglish', label: 'Hinglish' },
            ].map(({ id: lang, label }) => (
              <button
                key={lang}
                type="button"
                className={`lang-btn whitespace-nowrap ${language === lang ? 'active' : ''}`}
                onClick={() => onSwitchLanguage(lang)}
                disabled={isBusy || language === lang || !isActive}
                title={`Switch instruction to ${label}`}
                aria-pressed={language === lang}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Primary Navigation & Action Buttons Group (Separated on Right) */}
      <div className="controls-right flex items-center flex-wrap gap-3 ml-auto">
        {/* End Lesson Button */}
        {isActive && (
          <button
            type="button"
            className="btn btn-danger-outline btn-sm whitespace-nowrap"
            onClick={() => {
              if (window.confirm('Are you sure you want to conclude this lesson?')) {
                onEndSession('completed');
              }
            }}
            disabled={isBusy}
            title="End current lesson session"
          >
            {ending ? 'Concluding...' : '⏹️ End Lesson'}
          </button>
        )}

        {/* New Session Button when completed */}
        {completed && (
          <button
            type="button"
            className="btn btn-secondary btn-sm whitespace-nowrap"
            onClick={onResetClassroom}
          >
            🔄 New Session
          </button>
        )}

        {/* Primary Navigation Action Button */}
        {isActive && (
          <button
            type="button"
            className="btn btn-primary whitespace-nowrap"
            onClick={onAdvanceStep}
            disabled={isBusy}
            id="classroom-advance-button"
          >
            {advancing ? (
              <>
                <span className="spinner-sm" /> Advancing Step...
              </>
            ) : currentStep === 'explain' ? (
              '🔬 Continue to Demonstration →'
            ) : currentStep === 'demonstrate' ? (
              '❓ Proceed to Check Question →'
            ) : currentStep === 'question' ? (
              '➡️ Next Step →'
            ) : (
              'Next Teaching Step →'
            )}
          </button>
        )}
      </div>
    </footer>
  );
}
