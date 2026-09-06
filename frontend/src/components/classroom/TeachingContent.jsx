import React, { useState } from 'react';
import LoadingSpinner from '../LoadingSpinner';
import DiagramRenderer from './DiagramRenderer';
import { cleanTemplatedText } from './Blackboard';

/**
 * TeachingContent Component
 * The main learning surface for the AI Classroom.
 * Follows the required pedagogical information hierarchy:
 * 1. What am I learning? (Eyebrow: CORE CONCEPT, Concept Title, contextual line)
 * 2. Teacher explanation (24-28px heading, 16px body, 1.6 line height, max-width 700px)
 * 3. Visual / Demonstration (Subject-aware DiagramRenderer and/or code block)
 * 4. Key Takeaways (💡 Key takeaway with 2-4 bullets)
 * 5. Optional Analogy / Real-world Application
 * 6. Grounding / Source citations
 * 7. Step progression action
 */
export default function TeachingContent({
  delivery,
  step,
  currentStep,
  onAdvance,
  advancing,
  isBusy,
  currentConceptName,
  topic,
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!delivery) {
    return (
      <article className="teaching-content-surface teaching-content-empty" aria-label="Current Teaching Concept">
        <div className="empty-delivery-state text-center py-16">
          <span className="empty-icon text-4xl block mb-3">📖</span>
          <h3 className="text-lg font-bold text-slate-800">Awaiting teacher instruction...</h3>
          <p className="empty-text text-sm text-slate-500 max-w-sm mx-auto mt-1">
            Professor Teachie is calibrating your curriculum and preparing the visual materials.
          </p>
        </div>
      </article>
    );
  }

  const effectiveStep = delivery.step || currentStep || step || 'explain';
  const isDemonstration = effectiveStep === 'demonstrate';

  const title = delivery.title || delivery.concept_name || currentConceptName || 'Core Concept';

  // Domain selection: Only show code snippet if the topic is explicitly programming/CS
  const isProgrammingTopic = /python|javascript|code|programming|algorithm|data structure|sql|java|c\+\+|css|html|react|backend|frontend|software|tree|stack|queue|graph/i.test(
    (topic || '') + ' ' + (delivery.concept_name || '') + ' ' + (delivery.title || '')
  );
  const shouldShowCode = isProgrammingTopic && Boolean(delivery.code_snippet);

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

  // Helper to render bold **text** and bullet items gracefully
  const renderParagraph = (paragraph, idx) => {
    if (!paragraph || typeof paragraph !== 'string') return null;

    const lines = paragraph.split('\n');
    return (
      <div key={idx} className="delivery-paragraph-block mb-3">
        {lines.map((line, lineIdx) => {
          const trimmed = line.trim();
          const isBullet = /^[\*\-•]\s+/.test(trimmed);
          const rawText = isBullet ? trimmed.replace(/^[\*\-•]\s+/, '') : line;

          // Parse **bold** parts
          const parts = rawText.split(/(\*\*[^*]+\*\*)/g);
          const renderedLine = parts.map((part, partIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={partIdx} className="font-bold text-indigo-950">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return part;
          });

          if (isBullet) {
            return (
              <div key={lineIdx} className="flex items-start gap-2.5 my-1.5 pl-2">
                <span className="text-indigo-600 font-bold flex-shrink-0 mt-0.5">•</span>
                <span className="delivery-bullet-text text-slate-800 leading-relaxed text-[15.5px]">{renderedLine}</span>
              </div>
            );
          }

          return (
            <p key={lineIdx} className="delivery-paragraph text-slate-800 leading-relaxed my-2 text-[15.5px]">
              {renderedLine}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <article className="teaching-content-surface" aria-label="Current Teaching Concept">
      {/* 1. TOP OF CONTENT: Eyebrow + Concept Title + Contextual line */}
      <div className="teaching-content-header border-b border-slate-100 pb-4 mb-5">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-1.5">
          <span className="teaching-content-eyebrow text-[11px] font-extrabold uppercase tracking-widest text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100/80">
            {isDemonstration ? '🔬 DEMONSTRATION & APPLICATION' : '📖 CORE CONCEPT'}
          </span>
          <div className="flex items-center gap-2">
            {delivery.difficulty && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold capitalize">
                {delivery.difficulty}
              </span>
            )}
            {delivery.language && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold capitalize">
                🗣️ {delivery.language}
              </span>
            )}
          </div>
        </div>

        <h1 className="teaching-concept-title text-2xl md:text-[26px] font-extrabold text-slate-900 tracking-tight leading-snug m-0">
          {title}
        </h1>

        <p className="teaching-contextual-line text-sm text-slate-600 font-medium mt-1.5 mb-0">
          {isDemonstration
            ? "Let's see this concept in action through step-by-step application."
            : "Let's build the core understanding from fundamental principles."}
        </p>
      </div>

      {/* 2. EXPLANATION: Readable typography, line-height 1.6, max-width ~700px */}
      <div className="teaching-explanation-body max-w-[700px]">
        {delivery.content ? (
          delivery.content.split('\n\n').map(renderParagraph)
        ) : (
          <p className="delivery-paragraph text-slate-700 leading-relaxed text-[15.5px]">{delivery.content}</p>
        )}
      </div>

      {/* 3. VISUAL EXPLANATION: Subject-aware visual (tree / formula / physics / code) */}
      {(delivery.visual_description || shouldShowCode) && (
        <div className="teaching-visual-container mt-6 pt-5 border-t border-slate-100">
          <div className="teaching-visual-header flex items-center justify-between gap-2 mb-3">
            <span className="text-xs font-extrabold uppercase tracking-wider text-indigo-900 flex items-center gap-1.5">
              <span>🎨</span> VISUAL EXPLANATION
            </span>
          </div>

          {/* Interactive Subject-aware Diagram */}
          {delivery.visual_description && (
            <div className="teaching-diagram-card bg-slate-50/70 p-4 rounded-2xl border border-indigo-100/70 mb-3">
              <DiagramRenderer
                visualDescription={delivery.visual_description}
                diagramRequired={delivery.diagram_required}
                conceptName={title}
              />
            </div>
          )}

          {/* Code Demonstration Snippet (CS topics) */}
          {shouldShowCode && (
            <div className="teaching-code-card bg-slate-900 rounded-2xl p-4 border border-slate-800 text-slate-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-300">💻 Code Implementation</span>
                <button
                  type="button"
                  className="btn btn-xs btn-ghost text-slate-300 hover:text-white bg-slate-800/80 px-2 py-0.5 rounded text-xs"
                  onClick={handleCopyCode}
                  aria-label="Copy code to clipboard"
                >
                  {copied ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
              <pre className="m-0 overflow-x-auto text-xs font-mono text-emerald-400 leading-relaxed p-2 bg-slate-950/70 rounded-xl">
                <code>{delivery.code_snippet}</code>
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 4. KEY TAKEAWAY: Highlighted area with 2-4 bullets */}
      {delivery.key_takeaways && delivery.key_takeaways.length > 0 && (
        <div className="teaching-takeaways-highlight mt-6 p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-base" role="img" aria-label="Key takeaway">💡</span>
            <h3 className="text-sm font-bold text-indigo-950 m-0">Key takeaway</h3>
          </div>
          <ul className="space-y-1.5 m-0 pl-1 list-none">
            {delivery.key_takeaways.slice(0, 4).map((takeaway, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-700 leading-snug">
                <span className="text-indigo-600 font-bold flex-shrink-0 mt-0.5">•</span>
                <span>{cleanTemplatedText(takeaway)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. OPTIONAL ANALOGY / REAL-WORLD APPLICATION */}
      {(delivery.analogy || delivery.real_world_application) && (
        <div className="teaching-progressive-tools flex items-center flex-wrap gap-2 mt-4 pt-3 border-t border-slate-100">
          {delivery.analogy && (
            <details className="progressive-detail-item flex-1 min-w-[200px]">
              <summary className="progressive-summary-chip text-xs font-semibold px-3 py-1.5 rounded-xl bg-amber-50 text-amber-800 border border-amber-200 cursor-pointer hover:bg-amber-100 transition-all list-none flex items-center gap-1.5">
                <span>💡</span> See Intuitive Analogy
              </summary>
              <div className="progressive-content-box mt-2 p-3 bg-amber-50/60 rounded-xl border border-amber-100 text-xs text-slate-700 leading-relaxed">
                <strong className="text-amber-900 block mb-1">Analogy:</strong>
                {delivery.analogy}
              </div>
            </details>
          )}

          {delivery.real_world_application && (
            <details className="progressive-detail-item flex-1 min-w-[200px]">
              <summary className="progressive-summary-chip text-xs font-semibold px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-200 cursor-pointer hover:bg-emerald-100 transition-all list-none flex items-center gap-1.5">
                <span>🌍</span> Real-World Application
              </summary>
              <div className="progressive-content-box mt-2 p-3 bg-emerald-50/60 rounded-xl border border-emerald-100 text-xs text-slate-700 leading-relaxed">
                <strong className="text-emerald-900 block mb-1">Applied In Practice:</strong>
                {delivery.real_world_application}
              </div>
            </details>
          )}
        </div>
      )}

      {/* 6. SOURCE / GROUNDING: Compact collapsible indicator */}
      {delivery.sources && delivery.sources.length > 0 && (
        <div className="teaching-sources-box mt-5 pt-3 border-t border-slate-100">
          <button
            type="button"
            className="sources-toggle-btn flex items-center justify-between w-full text-left py-1 text-xs font-semibold text-indigo-700 hover:text-indigo-900"
            onClick={() => setSourcesOpen(!sourcesOpen)}
          >
            <span className="flex items-center gap-1.5">
              <span>📚 Based on your uploaded material</span>
              <span className="source-count-badge font-normal text-slate-500">({delivery.sources.length} sources)</span>
            </span>
            <span className="toggle-chevron text-[11px]">{sourcesOpen ? '▲ Hide' : 'View sources →'}</span>
          </button>

          {sourcesOpen && (
            <div className="sources-list flex flex-col gap-2 mt-2 p-3 bg-indigo-50/50 rounded-xl border border-indigo-100">
              {delivery.sources.map((src, i) => {
                const rawName = src.source_file || src.document_title || 'Uploaded Document';
                const cleanName = rawName.split(/[\\/]/).pop();
                const pageInfo = src.page ? ` — Page ${src.page}` : src.section ? ` — ${src.section}` : '';
                return (
                  <div key={i} className="source-item text-xs text-slate-700 flex items-start gap-1.5">
                    <span className="text-indigo-600 font-bold flex-shrink-0">•</span>
                    <div>
                      <strong className="text-slate-800">{cleanName}</strong>
                      <span className="text-slate-600">{pageInfo}</span>
                      {src.citation && (
                        <p className="text-slate-500 italic mt-0.5 text-[11px]">"{src.citation}"</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

