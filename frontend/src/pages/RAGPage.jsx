import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function RAGPage() {
  const { session, updateSession } = useTestSession();
  const [query, setQuery] = useState('What are the key concepts and mechanisms described?');
  const [topK, setTopK] = useState(5);
  const [materialId, setMaterialId] = useState(session.materialId || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchResults, setSearchResults] = useState(session.ragResults || []);
  const [groundedContext, setGroundedContext] = useState(session.groundedContext || null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError('Please enter a search query.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. Semantic Search
      const searchRes = await api.searchRAG({
        query: query.trim(),
        top_k: topK,
        material_id: materialId.trim() || null,
      });
      setSearchResults(searchRes.results);

      // 2. Grounded Context Construction
      const ctxRes = await api.getContextRAG({
        query: query.trim(),
        top_k: topK,
        material_id: materialId.trim() || null,
      });
      setGroundedContext(ctxRes);

      updateSession({
        ragResults: searchRes.results,
        groundedContext: ctxRes,
      });
    } catch (err) {
      setError(err.message || 'RAG retrieval failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🔍 RAG / Knowledge Grounding (Phase 3)</h1>
        <p className="page-description">
          Test semantic retrieval across indexed material chunks with vector embeddings and inspect formatted grounded context.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>
            <strong>RAG Error:</strong> {error}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">
          <span>Semantic Retrieval Query</span>
        </div>

        <form onSubmit={handleSearch}>
          <div className="form-group">
            <label className="form-label">Search Query</label>
            <input
              type="text"
              className="form-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. How does photosynthesis produce glucose?"
              disabled={loading}
            />
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Top K (1 - 20)</label>
              <input
                type="number"
                className="form-input"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                min="1"
                max="20"
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Filter by Material ID (Optional)</label>
              <input
                type="text"
                className="form-input"
                value={materialId}
                onChange={(e) => setMaterialId(e.target.value)}
                placeholder="Leave blank to search all materials"
                disabled={loading}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? '🔎 Searching Vector Store...' : '🔎 Run Semantic Search & Build Context'}
          </button>
        </form>
      </div>

      {groundedContext && (
        <div className="card">
          <div className="card-title">
            <span>Grounded Context for Teacher Prompt (Phase 3)</span>
            <span className="badge badge-pass">{groundedContext.citations?.length || 0} Citations</span>
          </div>

          <div className="form-group">
            <label className="form-label">Formatted Grounded Context String</label>
            <div className="code-block" style={{ maxHeight: '220px' }}>
              {groundedContext.formatted_context}
            </div>
          </div>

          {groundedContext.citations && groundedContext.citations.length > 0 && (
            <div style={{ marginTop: '12px' }}>
              <label className="form-label">Source Citations</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {groundedContext.citations.map((c, i) => (
                  <span key={i} className="badge badge-available">
                    [{c.citation_tag}] {c.filename} {c.page_number ? `(p. ${c.page_number})` : ''}{' '}
                    {c.slide_number ? `(slide ${c.slide_number})` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {searchResults && searchResults.length > 0 && (
        <div className="card">
          <div className="card-title">
            <span>Retrieved Chunks ({searchResults.length})</span>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Similarity / Score</th>
                  <th>Chunk ID</th>
                  <th>Source</th>
                  <th>Chapter / Section</th>
                  <th>Content</th>
                </tr>
              </thead>
              <tbody>
                {searchResults.map((res, idx) => (
                  <tr key={idx}>
                    <td>
                      <span className="badge badge-available">#{idx + 1}</span>
                    </td>
                    <td>
                      <strong>{typeof res.similarity_score === 'number' ? res.similarity_score.toFixed(4) : 'N/A'}</strong>
                    </td>
                    <td>
                      <code style={{ fontSize: '11px', color: '#38bdf8' }}>{res.chunk_id}</code>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{res.filename}</div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{res.material_id}</div>
                    </td>
                    <td>
                      {res.chapter || res.section ? (
                        <span>
                          {res.chapter} {res.section ? `> ${res.section}` : ''}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td>
                      <div style={{ maxWidth: '380px', fontSize: '12px' }}>{res.text}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
