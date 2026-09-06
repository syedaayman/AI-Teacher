import React, { useMemo } from 'react';
import { cleanTemplatedText } from './Blackboard';

/**
 * DiagramRenderer Component
 * Subject-Aware visual representation generator for:
 * - Mathematics: Equations, step-by-step solutions, coordinate/function relationships
 * - Physics: Physical formulas, processes, force/state diagrams
 * - Biology: Cellular & anatomical structures, biological cycle stages
 * - History: Chronological event timelines, historical milestones
 * - Programming: Execution flow, memory layout, call stack, architecture diagrams
 *
 * Adheres strictly to the Visual Safety Rule: Renders solely based on backend-provided
 * visual descriptions and concept names, never inventing facts or numbers.
 */
export default function DiagramRenderer({
  visualDescription,
  diagramRequired = false,
  conceptName = '',
}) {
  if (!visualDescription) return null;

  const cleanedNarrative = cleanTemplatedText(visualDescription);

  // Domain & Structural Analysis
  const analysis = useMemo(() => {
    const text = visualDescription.toLowerCase();
    const cName = (conceptName || '').toLowerCase();
    const combined = `${text} ${cName}`;

    // Detect subject domain
    let domain = 'GENERAL';
    if (/\b(equation|formula|matrix|graph|function|derivative|integral|algebra|calculus|f\(x\)|=|\+|-|\*|\/|step-by-step)\b/.test(combined)) {
      domain = 'MATHEMATICS';
    } else if (/\b(physics|force|velocity|acceleration|momentum|energy|gravity|circuit|thermodynamics|newton|joule|mass)\b/.test(combined)) {
      domain = 'PHYSICS';
    } else if (/\b(biology|cell|organelle|nucleus|membrane|mitochondria|photosynthesis|dna|rna|protein|enzyme|tissue|organ)\b/.test(combined)) {
      domain = 'BIOLOGY';
    } else if (/\b(history|century|timeline|era|dynasty|war|revolution|reign|treaty|chronological|bce|ce|\b\d{4}s?\b)\b/.test(combined)) {
      domain = 'HISTORY';
    } else if (/\b(code|programming|algorithm|array|stack|queue|tree|node|recursion|pointer|memory|index|complexity|loop|function|variable)\b/.test(combined)) {
      domain = 'PROGRAMMING';
    }

    // Detect layout structure
    let layout = 'CONCEPT_MODEL';
    if (
      domain === 'HISTORY' ||
      /\b(timeline|chronology|chronological|centuries|phases over time)\b/.test(text)
    ) {
      layout = 'TIMELINE';
    } else if (
      /\b(step|phase|stage|first|second|then|finally|->|-->|flow|pipeline)\b/.test(text) ||
      /\d+\.\s+/.test(visualDescription)
    ) {
      layout = 'SEQUENCE';
    } else if (/\b(versus|vs\.?|contrast|difference between|compared to|split)\b/.test(text)) {
      layout = 'COMPARISON';
    } else if (domain === 'MATHEMATICS' && (visualDescription.includes('=') || /\d+\.\s+/.test(visualDescription))) {
      layout = 'MATH_STEPS';
    } else if (domain === 'PROGRAMMING' && /\b(array|stack|call stack|memory|registers|slots|elements)\b/.test(combined)) {
      layout = 'EXECUTION_FLOW';
    }

    // Extract sequence items or steps
    let items = [];
    if (visualDescription.includes('->') || visualDescription.includes('-->')) {
      items = visualDescription
        .split(/-->|->/)
        .map((s) => s.trim().replace(/^[\d.)\s]+/, ''))
        .filter(Boolean)
        .slice(0, 5);
    } else {
      const numbered = visualDescription.match(/\d+[\.\)]\s*([^\d\.\)]+)/g);
      if (numbered && numbered.length >= 2) {
        items = numbered.map((m) => m.replace(/^\d+[\.\)]\s*/, '').trim()).filter(Boolean).slice(0, 5);
      } else {
        const sentences = visualDescription
          .split(/[.;]/)
          .map((s) => s.trim())
          .filter((s) => s.length > 4 && s.length < 100)
          .slice(0, 5);
        if (sentences.length >= 2) items = sentences;
      }
    }

    return { domain, layout, items };
  }, [visualDescription, conceptName]);

  const { domain, layout, items } = analysis;

  const getDomainBadge = () => {
    switch (domain) {
      case 'MATHEMATICS':
        return { icon: '📐', label: 'Mathematics Visual' };
      case 'PHYSICS':
        return { icon: '⚡', label: 'Physics Demonstration' };
      case 'BIOLOGY':
        return { icon: '🧬', label: 'Biological System' };
      case 'HISTORY':
        return { icon: '⏳', label: 'Historical Timeline' };
      case 'PROGRAMMING':
        return { icon: '💻', label: 'Execution & Architecture' };
      default:
        return { icon: '📊', label: diagramRequired ? 'Interactive Model' : 'Visual Mental Model' };
    }
  };

  const badge = getDomainBadge();

  return (
    <div
      className={`diagram-renderer-container domain-${domain.toLowerCase()} ${diagramRequired ? 'diagram-mandatory' : 'diagram-optional'}`}
      aria-label={`${badge.label} for ${conceptName || 'concept'}`}
    >
      {/* 1. Header with Domain Badge */}
      <div className="diagram-header">
        <div className="diagram-tag-group">
          <span className="diagram-icon">{badge.icon}</span>
          <span className="diagram-type-badge">{badge.label}</span>
        </div>
        {conceptName && <span className="diagram-concept-label">{conceptName}</span>}
      </div>

      {/* 2. Visual Model Canvas */}
      <div className="diagram-canvas-box">
        {/* CASE A: TIMELINE (History or Chronology) */}
        {layout === 'TIMELINE' && items.length >= 2 ? (
          <div className="timeline-visual-wrapper">
            <div className="timeline-horizontal-track">
              {items.map((milestone, idx) => (
                <div key={idx} className="timeline-milestone-node">
                  <div className="milestone-marker">
                    <span className="milestone-dot" />
                    <span className="milestone-index">Phase {idx + 1}</span>
                  </div>
                  <div className="milestone-card">
                    <p className="milestone-text">{milestone}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : layout === 'SEQUENCE' && items.length >= 2 ? (
          /* CASE B: SEQUENCE FLOW (Pipelines, Scientific Processes) */
          <div className="flow-diagram-wrapper">
            <svg
              className="diagram-svg sequence-svg"
              viewBox={`0 0 ${Math.max(items.length * 170, 360)} 96`}
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="flowNodeGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop stopColor="#1E293B" />
                  <stop offset="1" stopColor="#0F172A" />
                </linearGradient>
                <marker
                  id="flowArrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="#38BDF8" />
                </marker>
              </defs>

              {items.map((stepText, idx) => {
                const x = idx * 170 + 10;
                const nextX = (idx + 1) * 170 + 10;
                const isLast = idx === items.length - 1;

                return (
                  <g key={idx} className="flow-node-group">
                    {!isLast && (
                      <line
                        x1={x + 140}
                        y1={48}
                        x2={nextX - 8}
                        y2={48}
                        stroke="#38BDF8"
                        strokeWidth="2"
                        strokeDasharray="4 2"
                        markerEnd="url(#flowArrow)"
                      />
                    )}

                    <rect
                      x={x}
                      y={18}
                      width="140"
                      height="60"
                      rx="8"
                      fill="url(#flowNodeGrad)"
                      stroke="#38BDF8"
                      strokeWidth="1.5"
                      className="flow-node-rect"
                    />

                    <circle cx={x + 20} cy={34} r="9" fill="#0284C7" />
                    <text
                      x={x + 20}
                      y={38}
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontSize="10"
                      fontWeight="bold"
                    >
                      {idx + 1}
                    </text>

                    <text
                      x={x + 38}
                      y={38}
                      fill="#F8FAFC"
                      fontSize="11"
                      fontWeight="600"
                    >
                      Step {idx + 1}
                    </text>

                    <text
                      x={x + 12}
                      y={58}
                      fill="#94A3B8"
                      fontSize="9"
                    >
                      {stepText.slice(0, 22)}
                    </text>
                  </g>
                );
              })}
            </svg>

            <ol className="flow-steps-caption">
              {items.map((s, i) => (
                <li key={i} className="caption-step-item">
                  <strong className="step-num-badge">Step {i + 1}:</strong> {s}
                </li>
              ))}
            </ol>
          </div>
        ) : layout === 'EXECUTION_FLOW' ? (
          /* CASE C: PROGRAMMING / DATA STRUCTURE FLOW */
          <div className="programming-visual-wrapper">
            <div className="data-structure-board">
              <div className="board-lane memory-lane">
                <span className="lane-title">Memory / State Flow</span>
                <div className="lane-elements-row">
                  {items.length >= 2 ? (
                    items.map((item, idx) => (
                      <div key={idx} className="memory-cell">
                        <span className="cell-index">[{idx}]</span>
                        <span className="cell-val">{item.slice(0, 16)}</span>
                      </div>
                    ))
                  ) : (
                    <>
                      <div className="memory-cell">
                        <span className="cell-index">[0]</span>
                        <span className="cell-val">Initial State</span>
                      </div>
                      <div className="memory-arrow">→</div>
                      <div className="memory-cell active-cell">
                        <span className="cell-index">[1]</span>
                        <span className="cell-val">{conceptName ? conceptName.slice(0, 14) : 'Operation'}</span>
                      </div>
                      <div className="memory-arrow">→</div>
                      <div className="memory-cell">
                        <span className="cell-index">[2]</span>
                        <span className="cell-val">Output State</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : layout === 'MATH_STEPS' ? (
          /* CASE D: MATHEMATICS STEP-BY-STEP SOLUTION CARD */
          <div className="math-visual-wrapper">
            <div className="math-steps-card">
              <span className="math-steps-heading">Step-by-Step Derivation</span>
              <div className="math-steps-list">
                {items.length >= 2 ? (
                  items.map((step, idx) => (
                    <div key={idx} className="math-step-row">
                      <span className="math-step-badge">Step {idx + 1}</span>
                      <code className="math-step-expr">{step}</code>
                    </div>
                  ))
                ) : (
                  <div className="math-step-row">
                    <span className="math-step-badge">Formula / Formulation</span>
                    <code className="math-step-expr">{visualDescription}</code>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* CASE E: CONCEPTUAL STRUCTURAL MENTAL MODEL */
          <div className="concept-model-wrapper">
            {(() => {
              const words = (conceptName || 'Core Mechanism').split(' ');
              let line1 = conceptName || 'Core Mechanism';
              let line2 = '';
              if (words.length > 2 && conceptName.length > 15) {
                const mid = Math.ceil(words.length / 2);
                line1 = words.slice(0, mid).join(' ');
                line2 = words.slice(mid).join(' ');
              }

              return (
                <svg
                  className="diagram-svg concept-svg"
                  viewBox="0 0 520 120"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  style={{ width: '100%', maxHeight: '140px' }}
                >
                  <defs>
                    <linearGradient id="centerNodeGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop stopColor="#1E3A8A" />
                      <stop offset="1" stopColor="#0F172A" />
                    </linearGradient>
                    <linearGradient id="satelliteGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop stopColor="#1E293B" />
                      <stop offset="1" stopColor="#0F172A" />
                    </linearGradient>
                  </defs>

                  {/* Connecting Lines */}
                  <line x1="130" y1="60" x2="185" y2="60" stroke="#818CF8" strokeWidth="1.5" strokeDasharray="3 3" />
                  <line x1="335" y1="60" x2="390" y2="60" stroke="#818CF8" strokeWidth="1.5" strokeDasharray="3 3" />

                  {/* Satellite Node 1 (Foundation / Input) */}
                  <g>
                    <rect x="15" y="35" width="115" height="50" rx="8" fill="url(#satelliteGrad)" stroke="#38BDF8" strokeWidth="1.2" />
                    <text x="72" y="55" textAnchor="middle" fill="#38BDF8" fontSize="10" fontWeight="bold">Input / Foundation</text>
                    <text x="72" y="70" textAnchor="middle" fill="#94A3B8" fontSize="9">Prerequisite</text>
                  </g>

                  {/* Core Concept Node (Center) */}
                  <g>
                    <rect x="175" y="20" width="170" height="80" rx="10" fill="url(#centerNodeGrad)" stroke="#818CF8" strokeWidth="2" />
                    {line2 ? (
                      <>
                        <text x="260" y="48" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">
                          {line1}
                        </text>
                        <text x="260" y="64" textAnchor="middle" fill="#E0E7FF" fontSize="10.5" fontWeight="600">
                          {line2}
                        </text>
                      </>
                    ) : (
                      <text x="260" y="56" textAnchor="middle" fill="#FFFFFF" fontSize="11.5" fontWeight="bold">
                        {line1}
                      </text>
                    )}
                    <text x="260" y="86" textAnchor="middle" fill="#A5B4FC" fontSize="9.5">Active Concept</text>
                  </g>

                  {/* Satellite Node 2 (Application / Output) */}
                  <g>
                    <rect x="390" y="35" width="115" height="50" rx="8" fill="url(#satelliteGrad)" stroke="#34D399" strokeWidth="1.2" />
                    <text x="447" y="55" textAnchor="middle" fill="#34D399" fontSize="10" fontWeight="bold">Application State</text>
                    <text x="447" y="70" textAnchor="middle" fill="#94A3B8" fontSize="9">Target Outcome</text>
                  </g>
                </svg>
              );
            })()}
          </div>
        )}
      </div>

      {/* Pedagogical Visual Concept Summary */}
      {cleanedNarrative && (
        <div className="diagram-narrative-box">
          <span className="narrative-label">📌 Visual Concept:</span>
          <p className="narrative-text">{cleanedNarrative}</p>
        </div>
      )}
    </div>
  );
}
