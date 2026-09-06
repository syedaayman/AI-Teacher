import React, { useState } from 'react';
import DiagramRenderer from './DiagramRenderer';
import SourceCitations from './SourceCitations';

/**
 * Clean up templated text repetitions so concept titles fit naturally,
 * and strip prompt leakage like "Blackboard layout:", "Top section displays:", etc.
 */
export function cleanTemplatedText(text) {
  if (!text || typeof text !== 'string') return '';
  let cleaned = text
    .replace(/^(blackboard layout|visual layout|top section displays|bottom section shows|visual demonstration|visual mental model|blackboard notes|concept notes|key takeaways)[:\-–]\s*/i, '')
    .replace(/^([A-Za-z0-9\s_-]{3,50})[:\-–]\s*\1[:\-–]?\s*/i, '$1: ')
    .replace(/\s{2,}/g, ' ')
    .trim();
  cleaned = cleaned.replace(/^(displays|shows|illustrates)\s+/i, '');
  if (cleaned.length > 0) {
    cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }
  return cleaned;
}

/**
 * Blackboard Component (Upgraded for M2-4)
 * Authoritative digital teaching board for Member 2.
 * Renders:
 * - Interactive Diagram Models via DiagramRenderer (visual_description & diagram_required)
 * - Runnable Code Snippets with clipboard copy and language badges
 * - Key Takeaways bullet points with full line wrapping
 * - Intuitive Analogies without concept truncation
 * - Practical Real-World Applications
 * - Counter-Examples & Clarifying Traps
 * - RAG Source Citations (Material-Grounded vs. Topic-Only)
 */
export default function Blackboard({ delivery, currentConceptName, currentStep, topic }) {
  const [copied, setCopied] = useState(false);

  if (!delivery) {
    return (
      <aside className="blackboard-card min-w-0" aria-label="Digital Blackboard">
        <div className="blackboard-header flex flex-wrap items-center justify-between gap-2 min-w-0">
          <div className="board-title-group flex items-center gap-2 min-w-0 flex-wrap">
            <span className="board-icon flex-shrink-0">📋</span>
            <h4 className="board-title min-w-0 break-words whitespace-normal font-bold">
              Interactive Blackboard
            </h4>
          </div>
          <span className="board-status-badge min-w-0 whitespace-normal flex-shrink-0">Standby</span>
        </div>
        <div className="blackboard-empty min-w-0">
          <p className="blackboard-placeholder-text min-w-0 break-words whitespace-normal">
            Key takeaways, formulas, and visual models will appear here during instruction.
          </p>
        </div>
      </aside>
    );
  }

  const isDemonstration = delivery.step === 'demonstrate' || currentStep === 'demonstrate';
  const isQuestion = currentStep === 'question';
  const displayConcept = cleanTemplatedText(delivery.concept_name || currentConceptName || 'Concept Notes');

  // Domain selection: Only show code snippet if the topic is explicitly programming/CS
  const isProgrammingTopic = /python|javascript|code|programming|algorithm|data structure|sql|java|c\+\+|css|html|react|backend|frontend|software/i.test(
    (topic || '') + ' ' + (delivery.concept_name || '') + ' ' + (delivery.title || '')
  );
  const shouldShowCode = isProgrammingTopic && Boolean(delivery.code_snippet);

  const hasTakeaways = Array.isArray(delivery.key_takeaways) && delivery.key_takeaways.length > 0;
  const hasAnalogy = Boolean(delivery.analogy);
  const hasApplication = Boolean(delivery.real_world_application);
  const hasCounterExample = Boolean(delivery.counter_example);
  const hasVisual = Boolean(delivery.visual_description);
  const hasSources = Array.isArray(delivery.sources) && delivery.sources.length > 0;

  const handleCopyCode = () => {
    if (!delivery.code_snippet) return;
    try {
      navigator.clipboard.writeText(delivery.code_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.warn('Clipboard write failed:', e);
    }
  };

  return (
    <aside className="blackboard-card min-w-0" aria-label="Digital Blackboard">
      {/* 1. Blackboard Header */}
      <div className="blackboard-header flex flex-wrap items-center justify-between gap-2 min-w-0 mb-3 pb-2 border-b border-indigo-50">
        <div className="board-title-group flex items-center gap-2 min-w-0 flex-wrap">
          <span className="board-icon flex-shrink-0">📋</span>
          <h4 className="board-title min-w-0 break-words whitespace-normal font-bold text-slate-800">
            Current Idea: {displayConcept}
          </h4>
        </div>
        <span className="board-mode-tag text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
          {isQuestion ? '❓ Check Question' : isDemonstration ? '🔬 Demonstration' : '📖 Core Concept'}
        </span>
      </div>

      {/* 2. Focused Surface Content Area (Progressive Presentation) */}
      <div className="blackboard-surface min-w-0 flex flex-col gap-3">
        {/* Visual Graphic / Interactive Diagram */}
        {hasVisual && (
          <div className="board-section board-visual-section min-w-0">
            <DiagramRenderer
              visualDescription={delivery.visual_description}
              diagramRequired={delivery.diagram_required}
              conceptName={displayConcept}
            />
          </div>
        )}

        {/* Code Snippet Box (ONLY for programming topics) */}
        {shouldShowCode && (
          <div className="board-section board-code-section min-w-0">
            <div className="section-header code-header flex flex-wrap items-center justify-between gap-2 min-w-0 mb-1.5">
              <span className="section-tag code-tag text-xs font-bold text-slate-700">
                💻 Implementation
              </span>
              <button
                type="button"
                className="btn btn-xs btn-copy-code whitespace-nowrap"
                onClick={handleCopyCode}
                aria-label="Copy code to clipboard"
              >
                {copied ? '✓ Copied!' : '📋 Copy'}
              </button>
            </div>
            <pre className="board-code-block min-w-0 break-words overflow-x-auto text-xs" tabIndex="0">
              <code>{delivery.code_snippet}</code>
            </pre>
          </div>
        )}

        {/* Key Takeaways / Core Principles */}
        {hasTakeaways && (
          <div className="board-section board-takeaways-section min-w-0">
            <div className="section-header mb-1.5">
              <span className="section-tag takeaways-tag text-xs font-bold text-indigo-900 uppercase tracking-wide">
                🎯 Key Principles
              </span>
            </div>
            <ul className="board-takeaways-list min-w-0 space-y-1.5">
              {delivery.key_takeaways.slice(0, 3).map((point, idx) => (
                <li key={idx} className="takeaway-item flex items-start gap-2 min-w-0 text-sm">
                  <span className="takeaway-bullet text-indigo-600 font-bold flex-shrink-0" aria-hidden="true">•</span>
                  <span className="takeaway-text flex-1 min-w-0 break-words text-slate-700 leading-snug">
                    {cleanTemplatedText(point)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Progressive Disclosures: Analogy, Application & Trap (Section 6) */}
        {(hasAnalogy || (hasApplication && isDemonstration) || hasCounterExample) && (
          <div className="board-drawers-container flex flex-col gap-2 pt-2 border-t border-indigo-50">
            {hasAnalogy && !isQuestion && (
              <details className="board-drawer-detail">
                <summary className="board-drawer-summary text-xs font-semibold text-amber-800 bg-amber-50/80 px-2.5 py-1.5 rounded-lg border border-amber-200/70 cursor-pointer hover:bg-amber-100 transition-all flex items-center justify-between">
                  <span>💡 Intuitive Analogy</span>
                  <span className="text-[10px] text-amber-600">▼ Expand</span>
                </summary>
                <div className="board-drawer-body p-2.5 bg-amber-50/50 rounded-lg border border-amber-100 mt-1">
                  <p className="board-callout-text text-slate-700 text-xs leading-relaxed m-0">
                    {cleanTemplatedText(delivery.analogy)}
                  </p>
                </div>
              </details>
            )}

            {hasApplication && isDemonstration && (
              <details className="board-drawer-detail">
                <summary className="board-drawer-summary text-xs font-semibold text-emerald-800 bg-emerald-50/80 px-2.5 py-1.5 rounded-lg border border-emerald-200/70 cursor-pointer hover:bg-emerald-100 transition-all flex items-center justify-between">
                  <span>🚀 Real-World Relevance</span>
                  <span className="text-[10px] text-emerald-600">▼ Expand</span>
                </summary>
                <div className="board-drawer-body p-2.5 bg-emerald-50/50 rounded-lg border border-emerald-100 mt-1">
                  <p className="board-callout-text text-slate-700 text-xs leading-relaxed m-0">
                    {cleanTemplatedText(delivery.real_world_application)}
                  </p>
                </div>
              </details>
            )}

            {hasCounterExample && (
              <details className="board-drawer-detail">
                <summary className="board-drawer-summary text-xs font-semibold text-rose-800 bg-rose-50/80 px-2.5 py-1.5 rounded-lg border border-rose-200/70 cursor-pointer hover:bg-rose-100 transition-all flex items-center justify-between">
                  <span>⚠️ Common Pitfall / Trap</span>
                  <span className="text-[10px] text-rose-600">▼ Expand</span>
                </summary>
                <div className="board-drawer-body p-2.5 bg-rose-50/50 rounded-lg border border-rose-100 mt-1">
                  <p className="board-callout-text text-slate-700 text-xs leading-relaxed m-0">
                    {cleanTemplatedText(delivery.counter_example)}
                  </p>
                </div>
              </details>
            )}
          </div>
        )}

        {/* Source Citations (Clean, compact collapsible) */}
        {hasSources && (
          <div className="board-section board-sources-section min-w-0 pt-1 border-t border-slate-100">
            <SourceCitations sources={delivery.sources} />
          </div>
        )}
      </div>
    </aside>
  );
}
