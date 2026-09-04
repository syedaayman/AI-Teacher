import React, { useState, useEffect } from 'react';
import { api, getApiBaseUrl } from '../services/api';

const SUBSYSTEMS = [
  { name: 'FastAPI Backend', endpoint: '/api/v1/health', type: 'health' },
  { name: 'Material Processing', phase: 'Phase 2', status: 'AVAILABLE THROUGH API' },
  { name: 'RAG Retrieval & Vector Store', phase: 'Phase 3', status: 'AVAILABLE THROUGH API' },
  { name: 'Concept Graph & Lesson Planner', phase: 'Phase 4', status: 'AVAILABLE THROUGH API' },
  { name: 'Assessment & Misconception Engine', phase: 'Phase 5', status: 'AVAILABLE THROUGH API' },
  { name: 'Adaptive Learning Engine', phase: 'Phase 6', status: 'AVAILABLE THROUGH API' },
  { name: 'Learner Profile System', phase: 'Phase 7', status: 'AVAILABLE THROUGH API' },
];

export default function HealthPage() {
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [ragStats, setRagStats] = useState(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHealth();
      setHealthData(data);
      try {
        const stats = await api.getStatsRAG();
        setRagStats(stats);
      } catch {
        // Non-critical if RAG stats fails
      }
    } catch (err) {
      setError(err.formattedMessage || err.message || 'Failed to connect to backend');
      setHealthData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const isConnected = !!healthData && healthData.status === 'ok';

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🏥 System Health & Subsystems</h1>
        <p className="page-description">
          Inspect FastAPI backend connectivity, service metadata, and subsystem availability.
        </p>
        <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
          Active API Base Host: <code style={{ color: '#38bdf8' }}>{getApiBaseUrl()}</code>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div style={{ width: '100%' }}>
            <strong>Connection Error:</strong>
            <pre style={{ margin: '6px 0 0 0', whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '11px' }}>
              {error}
            </pre>
            <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              Ensure the FastAPI server is running with: <code>uvicorn main:app --host 0.0.0.0 --port 8000</code>
            </div>
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <div className="card-title">
            <span>FastAPI Server Status</span>
            <button className="btn btn-secondary btn-sm" onClick={fetchHealth} disabled={loading}>
              {loading ? 'Checking...' : '🔄 Refresh'}
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>API Status:</span>
              <span className={`badge ${isConnected ? 'badge-connected' : 'badge-disconnected'}`}>
                {isConnected ? '● CONNECTED' : '● DISCONNECTED'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Service:</span>
              <strong style={{ fontFamily: 'monospace' }}>{healthData?.service || 'ai-brain'}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Version:</span>
              <span style={{ fontFamily: 'monospace' }}>{healthData?.version || '0.1.0'}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Timestamp:</span>
              <span style={{ fontSize: '11px', fontFamily: 'monospace' }}>
                {healthData?.timestamp ? new Date(healthData.timestamp).toLocaleString() : 'N/A'}
              </span>
            </div>

            {ragStats && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Indexed Chunks in Vector Store:</span>
                <span className="badge badge-available">{ragStats.total_vectors} chunks</span>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-title">
            <span>Subsystems Status</span>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Subsystem</th>
                <th>Phase</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {SUBSYSTEMS.map((sub, idx) => (
                <tr key={idx}>
                  <td>
                    <strong>{sub.name}</strong>
                  </td>
                  <td>
                    <span className="phase-badge">{sub.phase || 'Phase 1'}</span>
                  </td>
                  <td>
                    {sub.type === 'health' ? (
                      <span className={`badge ${isConnected ? 'badge-operational' : 'badge-disconnected'}`}>
                        {isConnected ? 'OPERATIONAL' : 'DISCONNECTED'}
                      </span>
                    ) : (
                      <span className="badge badge-available">{sub.status}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
