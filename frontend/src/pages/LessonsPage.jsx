import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function LessonsPage() {
  const { session, updateSession } = useTestSession();
  const [mode, setMode] = useState(session.materialDocument ? 'grounded' : 'topic');
  const [topic, setTopic] = useState('Data Structures and Algorithms');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [syllabus, setSyllabus] = useState(session.syllabus || null);

  const handlePlan = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let plan;
      if (mode === 'grounded') {
        if (!session.materialDocument) {
          throw new Error('No material document found in test session. Please process a material in Step 2 first.');
        }
        plan = await api.planLessons({
          document: session.materialDocument,
          title: title.trim() || undefined,
        });
      } else {
        if (!topic.trim()) {
          throw new Error('Please enter a topic.');
        }
        plan = await api.planLessons({
          topic: topic.trim(),
          title: title.trim() || undefined,
        });
      }

      setSyllabus(plan);
      updateSession({
        syllabus: plan,
        selectedLesson: plan.lessons?.[0] || null,
      });
    } catch (err) {
      setError(err.message || 'Lesson planning failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectLesson = (lsn) => {
    updateSession({ selectedLesson: lsn });
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📚 Lesson Planner & Syllabus (Phase 4)</h1>
        <p className="page-description">
          Generate pedagogically sequenced course lessons with deterministic IDs and prerequisite tracking.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>
            <strong>Planning Error:</strong> {error}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">
          <span>Syllabus Generation Mode</span>
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

        <form onSubmit={handlePlan}>
          <div className="grid-2">
            {mode === 'topic' ? (
              <div className="form-group">
                <label className="form-label">Topic</label>
                <input
                  type="text"
                  className="form-input"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Fundamental Python Programming"
                  disabled={loading}
                />
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">Active Test Session Material</label>
                <input
                  type="text"
                  className="form-input"
                  value={session.materialFilename || 'No file processed yet'}
                  disabled
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Custom Syllabus Title (Optional)</label>
              <input
                type="text"
                className="form-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Leave blank for automatic title"
                disabled={loading}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? '📚 Generating Syllabus & Sequencing Lessons...' : '📚 Generate Sequenced Syllabus'}
          </button>
        </form>
      </div>

      {syllabus && (
        <div className="card">
          <div className="card-title">
            <span>Syllabus: {syllabus.title}</span>
            <span className="badge badge-pass">{syllabus.lessons?.length || 0} Lessons</span>
          </div>

          <div style={{ marginBottom: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            Syllabus ID: <code style={{ color: '#38bdf8' }}>{syllabus.syllabus_id}</code> | Mode:{' '}
            <span className="phase-badge">{syllabus.is_grounded ? 'Grounded' : 'Topic-Only'}</span> | Total Lessons:{' '}
            <strong>{syllabus.total_lessons}</strong>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {syllabus.lessons?.map((lsn, idx) => (
              <div
                key={lsn.lesson_id}
                style={{
                  padding: '16px',
                  background: session.selectedLesson?.lesson_id === lsn.lesson_id ? 'var(--bg-card-alt)' : 'var(--bg-primary)',
                  border: session.selectedLesson?.lesson_id === lsn.lesson_id ? '1px solid #38bdf8' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="badge badge-available">Lesson {lsn.sequence_order || idx + 1}</span>
                    <strong style={{ fontSize: '14px' }}>{lsn.title}</strong>
                    <span className="phase-badge">{lsn.difficulty}</span>
                  </div>

                  <button
                    className={`btn btn-sm ${session.selectedLesson?.lesson_id === lsn.lesson_id ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleSelectLesson(lsn)}
                  >
                    {session.selectedLesson?.lesson_id === lsn.lesson_id ? '✓ Selected' : 'Select Lesson'}
                  </button>
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  ID: <code style={{ color: '#38bdf8' }}>{lsn.lesson_id}</code>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  {lsn.summary}
                </div>

                <div className="grid-2" style={{ fontSize: '12px' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Concepts Covered:</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                      {lsn.concept_ids?.map((cid) => (
                        <span key={cid} className="badge badge-available" style={{ fontSize: '10px' }}>
                          {cid}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Prerequisite Lessons:</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                      {lsn.prerequisite_lesson_ids?.length > 0 ? (
                        lsn.prerequisite_lesson_ids.map((pid) => (
                          <span key={pid} className="badge badge-warning" style={{ fontSize: '10px' }}>
                            {pid}
                          </span>
                        ))
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>None (Starting Lesson)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
