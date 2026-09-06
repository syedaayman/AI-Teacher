import React, { useState } from 'react';
import { useClassroom } from '../../context/ClassroomContext';

/**
 * Clean up templated text repetitions so concept titles fit naturally
 */
function cleanConceptName(rawName) {
  if (!rawName || typeof rawName !== 'string') return '';
  return rawName
    .replace(/^([A-Za-z0-9\s_-]{3,50})[:\-–]\s*\1[:\-–]?\s*/i, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/**
 * LearningJourney Component
 * Displays "YOUR LEARNING JOURNEY" adhering strictly to Rule 10 & 13:
 * - ✓ Strong (Completed concept)
 * - ● Learning (Active concept)
 * - ○ Upcoming (Planned future concept)
 * Visualizes the authentic concept sequence with complete text wrapping and no truncation.
 */
export default function LearningJourney({ collapsedDefault = false, compact = false, strip = false }) {
  const {
    topic,
    concepts = [],
    conceptNames = {},
    conceptIndex = 0,
    totalConcepts = 0,
    currentConceptName,
  } = useClassroom();

  const [isExpanded, setIsExpanded] = useState(!collapsedDefault);

  // If no concepts yet, or only 1 generic concept, construct from concept names or display current
  const items = concepts.length > 0
    ? concepts.map((cid, idx) => {
        const rawName = conceptNames[cid] || cid.replace(/_/g, ' ').replace(/^cpt\s*/i, '');
        const name = cleanConceptName(rawName);
        const status = idx < conceptIndex ? 'strong' : idx === conceptIndex ? 'learning' : 'upcoming';
        return {
          id: cid,
          name,
          status,
          formattedLabel: `${name} - ${status}`,
        };
      })
    : totalConcepts > 0
    ? Array.from({ length: totalConcepts }).map((_, idx) => {
        const rawName = idx === conceptIndex ? (currentConceptName || `Concept ${idx + 1}`) : `Concept ${idx + 1}`;
        const name = cleanConceptName(rawName);
        const status = idx < conceptIndex ? 'strong' : idx === conceptIndex ? 'learning' : 'upcoming';
        return {
          id: `c_${idx}`,
          name,
          status,
          formattedLabel: `${name} - ${status}`,
        };
      })
    : [];

  if (items.length === 0) return null;

  if (strip) {
    return (
      <nav className="classroom-progress-strip mb-4" aria-label="Curriculum Progress Trail">
        <div className="strip-track flex items-center flex-wrap gap-2 py-2 px-3 bg-white/95 rounded-xl border border-indigo-100 shadow-xs">
          {items.map((item, idx) => {
            const isLearning = item.status === 'learning';
            const isStrong = item.status === 'strong';
            const padNum = String(idx + 1).padStart(2, '0');
            return (
              <React.Fragment key={item.id || idx}>
                <div
                  className={`strip-item flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                    isLearning
                      ? 'bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-200'
                      : isStrong
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-slate-50 text-slate-500 border border-slate-200'
                  }`}
                  title={`${padNum} ${item.name} (${item.status})`}
                >
                  <span className="strip-num opacity-75">{padNum}</span>
                  <span className="strip-name font-medium truncate max-w-[140px]">{item.name}</span>
                  <span className="strip-status-icon">
                    {isStrong ? '✓' : isLearning ? '●' : '○'}
                  </span>
                </div>
                {idx < items.length - 1 && (
                  <span className="strip-arrow text-slate-300 font-bold text-xs" aria-hidden="true">→</span>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </nav>
    );
  }

  if (compact) {
    return (
      <div className="compact-journey-card mt-3 p-3 bg-white/95 rounded-2xl border border-indigo-100 shadow-sm">
        <div className="flex items-center justify-between text-xs text-slate-600 font-bold mb-2">
          <span className="flex items-center gap-1.5 text-indigo-900">
            <span>🗺️</span> Learning Path
          </span>
          <span className="text-indigo-600">
            {conceptIndex + 1} of {items.length} Concepts
          </span>
        </div>
        <div className="compact-journey-pills flex flex-wrap gap-1.5">
          {items.map((item, idx) => {
            const isLearning = item.status === 'learning';
            const isStrong = item.status === 'strong';
            return (
              <div
                key={item.id || idx}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                  isLearning
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : isStrong
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-slate-100 text-slate-500'
                }`}
                title={item.name}
              >
                <span>{isStrong ? '✓' : isLearning ? '●' : `${idx + 1}`}</span>
                <span className="truncate max-w-[110px]">{item.name}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <aside className="learning-journey-panel min-w-0" aria-label="Learning Journey">
      <div
        className="journey-header flex flex-wrap items-center justify-between gap-2 min-w-0 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex="0"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
        aria-expanded={isExpanded}
      >
        <div className="journey-title-group flex items-center gap-2 min-w-0 flex-1 flex-wrap">
          <span className="journey-icon flex-shrink-0" aria-hidden="true">🗺️</span>
          <div className="min-w-0 flex-1">
            <h4 className="journey-title min-w-0 break-words whitespace-normal font-bold">
              YOUR LEARNING JOURNEY
            </h4>
            {topic && (
              <span className="journey-topic-name min-w-0 break-words whitespace-normal block text-xs text-slate-500">
                {cleanConceptName(topic)}
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          className="btn-toggle-journey flex-shrink-0"
          aria-label={isExpanded ? 'Collapse learning journey' : 'Expand learning journey'}
        >
          {isExpanded ? '▲' : '▼'}
        </button>
      </div>

      {isExpanded && (
        <div className="journey-content min-w-0">
          <div className="journey-legend flex flex-wrap items-center gap-3">
            <span className="legend-item whitespace-normal"><span className="symbol strong">✓</span> Strong</span>
            <span className="legend-item whitespace-normal"><span className="symbol learning">●</span> Learning</span>
            <span className="legend-item whitespace-normal"><span className="symbol upcoming">○</span> Upcoming</span>
          </div>

          <ol className="journey-nodes-list min-w-0">
            {items.map((item, idx) => {
              const isStrong = item.status === 'strong';
              const isLearning = item.status === 'learning';
              const statusText = isStrong ? 'Strong' : isLearning ? 'Active Concept' : 'Upcoming';

              return (
                <li
                  key={item.id || idx}
                  className={`journey-node node-${item.status} flex items-start gap-3 min-w-0`}
                  aria-current={isLearning ? 'step' : undefined}
                  aria-label={`${item.name} - ${item.status}`}
                  title={`${item.name} - ${item.status}`}
                >
                  <div className="node-marker flex-shrink-0" aria-hidden="true">
                    {isStrong ? (
                      <span className="marker-icon marker-strong">✓</span>
                    ) : isLearning ? (
                      <span className="marker-icon marker-learning">●</span>
                    ) : (
                      <span className="marker-icon marker-upcoming">○</span>
                    )}
                    {idx < items.length - 1 && <div className="marker-stem" />}
                  </div>

                  <div className="node-details flex-1 min-w-0 flex flex-wrap items-center justify-between gap-1">
                    <span className="node-name min-w-0 break-words whitespace-normal font-medium text-sm">
                      {item.name}
                    </span>
                    <span className="node-badge min-w-0 whitespace-normal flex-shrink-0">
                      {statusText}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </aside>
  );
}
