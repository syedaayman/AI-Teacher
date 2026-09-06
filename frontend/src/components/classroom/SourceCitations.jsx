import React, { useState } from 'react';

/**
 * SourceCitations Component
 * Displays material-grounded learning sources with high trust and zero technical jargon.
 * Strictly adheres to Rule 6:
 * - Shows subtle indicator: "Teaching from your material"
 * - Clean metadata badges: Filename, Page number, Chapter, Slide, Section
 * - NEVER displays: RAG, embeddings, vector database, retrieval, similarity score.
 */
export default function SourceCitations({ sources = [] }) {
  const [expanded, setExpanded] = useState(false);
  const hasSources = Array.isArray(sources) && sources.length > 0;

  if (!hasSources) {
    return (
      <div className="grounding-indicator topic-mode" aria-label="Curriculum Grounding">
        <div className="grounding-badge">
          <span className="grounding-icon">🌱</span>
          <div className="grounding-info">
            <span className="grounding-title">Curated Topic Curriculum</span>
            <span className="grounding-sub">Structured foundational sequence</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grounding-indicator material-mode" aria-label="Curriculum Grounding">
      <div
        className="grounding-header"
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex="0"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setExpanded(!expanded);
          }
        }}
        aria-expanded={expanded}
      >
        <div className="grounding-badge">
          <span className="grounding-icon">📖</span>
          <div className="grounding-info">
            <span className="grounding-title">Teaching from your material</span>
            <span className="grounding-sub">
              {sources.length} verified {sources.length === 1 ? 'source reference' : 'source references'} from your uploaded notes
            </span>
          </div>
        </div>
        <button
          type="button"
          className="btn-expand-citations"
          aria-label={expanded ? 'Hide source citations' : 'Show source citations'}
        >
          {expanded ? '▲ Hide Sources' : '▼ View Sources'}
        </button>
      </div>

      {expanded && (
        <div className="citations-list">
          {sources.map((src, idx) => {
            const fileName =
              src.filename ||
              src.source_file ||
              src.document_title ||
              `Study Material #${idx + 1}`;
            const page =
              src.page_number !== undefined && src.page_number !== null
                ? `Page ${src.page_number}`
                : null;
            const slide =
              src.slide_number !== undefined && src.slide_number !== null
                ? `Slide ${src.slide_number}`
                : null;
            const chapter = src.chapter ? `Chapter ${src.chapter}` : null;
            const section = src.section ? `Section ${src.section}` : null;

            return (
              <div key={idx} className="citation-card">
                <div className="citation-card-header">
                  <span className="citation-num">#{idx + 1}</span>
                  <strong className="citation-filename" title={fileName}>
                    {fileName}
                  </strong>
                  <span className="citation-verified-badge">✓ Verified Source</span>
                </div>

                <div className="citation-meta-row">
                  {page && <span className="citation-tag tag-page">📄 {page}</span>}
                  {slide && <span className="citation-tag tag-slide">📽️ {slide}</span>}
                  {chapter && <span className="citation-tag tag-chapter">📖 {chapter}</span>}
                  {section && <span className="citation-tag tag-section">🔖 {section}</span>}
                </div>

                {src.chunk_text && (
                  <blockquote className="citation-snippet">
                    "{src.chunk_text.slice(0, 160)}..."
                  </blockquote>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
