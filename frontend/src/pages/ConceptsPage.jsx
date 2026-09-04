import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function ConceptsPage() {
  const { session, updateSession } = useTestSession();
  const [mode, setMode] = useState(session.materialDocument ? 'grounded' : 'topic');
  const [topic, setTopic] = useState('Data Structures and Algorithms');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [concepts, setConcepts] = useState(session.concepts || []);
  const [graphData, setGraphData] = useState(session.conceptGraph ? { graph: session.conceptGraph, topological_order: session.topologicalOrder } : null);

  const handleExtract = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // 1. Extract Concepts
      let extractedList;
      if (mode === 'grounded') {
        if (!session.materialDocument) {
          throw new Error('No material document found in test session. Please process a material in Step 2 first.');
        }
        extractedList = await api.extractConcepts({
          document: session.materialDocument,
          material_id: session.materialId,
        });
      } else {
        if (!topic.trim()) {
          throw new Error('Please enter a topic.');
        }
        extractedList = await api.extractConcepts({
          topic: topic.trim(),
        });
      }

      setConcepts(extractedList);

      // 2. Build Concept Graph & Topological Order
      let gRes = null;
      if (extractedList && extractedList.length > 0) {
        gRes = await api.buildConceptGraph(extractedList);
        setGraphData(gRes);
      }

      updateSession({
        concepts: extractedList,
        conceptGraph: gRes?.graph || null,
        topologicalOrder: gRes?.topological_order || [],
        selectedConcept: extractedList[0] || null,
      });
    } catch (err) {
      setError(err.message || 'Concept extraction failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectConcept = (cpt) => {
    updateSession({ selectedConcept: cpt });
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🧩 Concepts & Concept Graph (Phase 4)</h1>
        <p className="page-description">
          Extract structured pedagogical concepts, validate prerequisite relationships, and verify topological sorting.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>
            <strong>Concept Error:</strong> {error}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">
          <span>Concept Extraction Mode</span>
        </div>

        <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input
              type="radio"
              name="mode"
              value="topic"
              checked={mode === 'topic'}
              onChange={() => setMode('topic')}
            />
            Topic-Only Mode
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input
              type="radio"
              name="mode"
              value="grounded"
              checked={mode === 'grounded'}
              onChange={() => setMode('grounded')}
            />
            Material-Grounded Mode {session.materialFilename ? `(${session.materialFilename})` : '(No file loaded)'}
          </label>
        </div>

        <form onSubmit={handleExtract}>
          {mode === 'topic' ? (
            <div className="form-group">
              <label className="form-label">Instructional Topic</label>
              <input
                type="text"
                className="form-input"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Object Oriented Programming in Python"
                disabled={loading}
              />
            </div>
          ) : (
            <div className="alert alert-info">
              <span>📄</span>
              <div>
                Extracting concepts from active test session material: <strong>{session.materialFilename || 'None'}</strong>{' '}
                ({session.materialDocument?.chunks?.length || 0} chunks)
              </div>
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? '⚙️ Extracting Concepts & Validating Graph...' : '🧩 Extract Concepts & Build Graph'}
          </button>
        </form>
      </div>

      {graphData && (
        <div className="card">
          <div className="card-title">
            <span>Validated Pedagogical Topological Sequence</span>
            <span className="badge badge-pass">DFS Cycle-Free</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {graphData.topological_order.map((cpt, idx) => (
              <div
                key={cpt.concept_id}
                style={{
                  padding: '12px 16px',
                  background: session.selectedConcept?.concept_id === cpt.concept_id ? 'var(--bg-card-alt)' : 'var(--bg-primary)',
                  border: session.selectedConcept?.concept_id === cpt.concept_id ? '1px solid #38bdf8' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span className="badge badge-available">Step {idx + 1}</span>
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{cpt.name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      ID: <code style={{ color: '#38bdf8' }}>{cpt.concept_id}</code> | Difficulty: {cpt.difficulty}
                    </div>
                    {cpt.prerequisite_concept_ids?.length > 0 && (
                      <div style={{ fontSize: '11px', color: '#f59e0b', marginTop: '2px' }}>
                        Prerequisites: {cpt.prerequisite_concept_ids.join(', ')}
                      </div>
                    )}
                  </div>
                </div>

                <button
                  className={`btn btn-sm ${session.selectedConcept?.concept_id === cpt.concept_id ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleSelectConcept(cpt)}
                >
                  {session.selectedConcept?.concept_id === cpt.concept_id ? '✓ Selected' : 'Select for Testing'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {concepts && concepts.length > 0 && (
        <div className="card">
          <div className="card-title">
            <span>Extracted Concepts List ({concepts.length})</span>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Concept ID</th>
                  <th>Name</th>
                  <th>Difficulty</th>
                  <th>Description</th>
                  <th>Objectives</th>
                  <th>Prerequisites</th>
                </tr>
              </thead>
              <tbody>
                {concepts.map((c) => (
                  <tr key={c.concept_id}>
                    <td>
                      <code style={{ fontSize: '11px', color: '#38bdf8' }}>{c.concept_id}</code>
                    </td>
                    <td>
                      <strong>{c.name}</strong>
                    </td>
                    <td>
                      <span className="phase-badge">{c.difficulty}</span>
                    </td>
                    <td>
                      <div style={{ maxWidth: '280px', fontSize: '12px' }}>{c.description}</div>
                    </td>
                    <td>
                      <ul style={{ paddingLeft: '14px', fontSize: '11px' }}>
                        {c.learning_objectives?.map((obj, oi) => (
                          <li key={oi}>{obj}</li>
                        ))}
                      </ul>
                    </td>
                    <td>
                      {c.prerequisite_concept_ids?.length > 0 ? (
                        c.prerequisite_concept_ids.map((p, pi) => (
                          <span key={pi} className="badge badge-warning" style={{ margin: '2px' }}>
                            {p}
                          </span>
                        ))
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>None</span>
                      )}
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
