import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function LearnerProfilePage() {
  const { session, updateSession } = useTestSession();

  // Create form state
  const [learnerId, setLearnerId] = useState(session.learnerId || 'dev_learner_01');
  const [name, setName] = useState('Alex');
  const [language, setLanguage] = useState('english');
  const [goal, setGoal] = useState('Master core computer science algorithms');
  const [difficulty, setDifficulty] = useState('intermediate');
  const [totalLessons, setTotalLessons] = useState(10);

  // Lesson & assessment quick actions
  const [lessonIdToRecord, setLessonIdToRecord] = useState(session.selectedLesson?.lesson_id || 'lsn_intro_01');
  const [assessmentScoreToRecord, setAssessmentScoreToRecord] = useState(0.85);

  // Profile data & UI states
  const [profile, setProfile] = useState(session.learnerProfile || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const fetchProfile = async (idToFetch = learnerId) => {
    if (!idToFetch) return;
    setLoading(true);
    setError(null);
    try {
      const p = await api.getProfile(idToFetch);
      setProfile(p);
      updateSession({ learnerProfile: p, learnerId: p.learner_id });
    } catch (err) {
      if (err.status === 404 || err.status === 400) {
        setProfile(null);
      } else {
        setError(err.message || 'Failed to fetch learner profile');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile(learnerId);
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const created = await api.createProfile({
        learner_id: learnerId.trim(),
        name: name.trim() || undefined,
        preferred_language: language,
        learning_goal: goal.trim() || undefined,
        preferred_difficulty: difficulty,
        total_lessons: Number(totalLessons),
      });

      setProfile(created);
      setSuccessMsg(`Learner profile for '${created.learner_id}' created successfully!`);
      updateSession({
        learnerProfile: created,
        learnerId: created.learner_id,
      });
    } catch (err) {
      setError(err.message || 'Failed to create profile');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePreferences = async () => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.updatePreferences({
        learner_id: profile.learner_id,
        preferred_language: language,
        preferred_difficulty: difficulty,
        learning_goal: goal.trim() || undefined,
      });
      setProfile(updated);
      setSuccessMsg('Preferences updated successfully!');
      updateSession({ learnerProfile: updated });
    } catch (err) {
      setError(err.message || 'Failed to update preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncMastery = async () => {
    if (!profile) return;
    if (!session.conceptMastery) {
      setError('No ConceptMastery found in test session. Run Adaptive simulation first.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const updated = await api.updateProfileMastery({
        learner_id: profile.learner_id,
        concept_mastery: session.conceptMastery,
      });
      setProfile(updated);
      setSuccessMsg(`Synchronized mastery for concept '${session.conceptMastery.concept_id}'!`);
      updateSession({ learnerProfile: updated });
    } catch (err) {
      setError(err.message || 'Failed to sync mastery');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordLesson = async () => {
    if (!profile || !lessonIdToRecord.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.recordLessonCompletion({
        learner_id: profile.learner_id,
        lesson_id: lessonIdToRecord.trim(),
      });
      setProfile(updated);
      setSuccessMsg(`Recorded completion for lesson '${lessonIdToRecord}'!`);
      updateSession({ learnerProfile: updated });
    } catch (err) {
      setError(err.message || 'Failed to record lesson');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordAssessment = async () => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.recordAssessmentResult({
        learner_id: profile.learner_id,
        score: Number(assessmentScoreToRecord),
      });
      setProfile(updated);
      setSuccessMsg(`Recorded assessment score ${assessmentScoreToRecord}!`);
      updateSession({ learnerProfile: updated });
    } catch (err) {
      setError(err.message || 'Failed to record assessment');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">👤 Learner Profile System (Phase 7)</h1>
        <p className="page-description">
          Inspect and manage learner identity, instructional preferences, aggregate mastery metrics, and curriculum progress.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>{error}</div>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success">
          <span>✓</span>
          <div>{successMsg}</div>
        </div>
      )}

      <div className="grid-2">
        {/* CREATE / INITIALIZE PROFILE */}
        <div className="card">
          <div className="card-title">
            <span>Initialize / Create Profile</span>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => fetchProfile(learnerId)}
              disabled={loading}
            >
              🔄 Fetch Profile
            </button>
          </div>

          <form onSubmit={handleCreate}>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Learner ID</label>
                <input
                  type="text"
                  className="form-input"
                  value={learnerId}
                  onChange={(e) => setLearnerId(e.target.value)}
                  placeholder="e.g. dev_learner_01"
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Name / Handle</label>
                <input
                  type="text"
                  className="form-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Alex"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Preferred Language</label>
                <select
                  className="form-select"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={loading}
                >
                  <option value="english">English</option>
                  <option value="hindi">Hindi</option>
                  <option value="hinglish">Hinglish</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Preferred Difficulty Baseline</label>
                <select
                  className="form-select"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  disabled={loading}
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Learning Goal</label>
              <input
                type="text"
                className="form-input"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. Complete university data structures curriculum"
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Total Lessons</label>
              <input
                type="number"
                className="form-input"
                value={totalLessons}
                onChange={(e) => setTotalLessons(Number(e.target.value))}
                min="0"
                disabled={loading}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
              <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1 }}>
                {loading ? 'Creating...' : '➕ Create / Reset Profile'}
              </button>
              {profile && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleUpdatePreferences}
                  disabled={loading}
                >
                  Update Preferences
                </button>
              )}
            </div>
          </form>
        </div>

        {/* PROFILE STATE DISPLAY */}
        <div className="card">
          <div className="card-title">
            <span>Profile Summary & Metrics</span>
            {profile && <span className="badge badge-pass">ACTIVE</span>}
          </div>

          {profile ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
              <div className="grid-2">
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Learner:</span>{' '}
                  <strong>{profile.name || profile.learner_id}</strong> (<code>{profile.learner_id}</code>)
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Language:</span>{' '}
                  <span className="phase-badge">{profile.preferred_language}</span>
                </div>
              </div>

              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Goal:</span>{' '}
                <span style={{ color: 'var(--text-primary)' }}>{profile.learning_goal || 'None'}</span>
              </div>

              <div className="grid-3" style={{ padding: '10px', background: 'var(--bg-primary)', borderRadius: '6px' }}>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>OVERALL MASTERY</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: '#38bdf8' }}>
                    {(profile.overall_mastery * 100).toFixed(1)}%
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ASSESSMENT AVG</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: '#34d399' }}>
                    {(profile.average_score * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>({profile.assessment_count} tests)</div>
                </div>

                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>LESSON PROGRESS</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: '#f59e0b' }}>
                    {profile.completed_lessons?.length || 0} / {profile.total_lessons}
                  </div>
                </div>
              </div>

              {/* Strengths & Weak Areas */}
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Strengths (Proficient/Mastered):</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                  {profile.strengths?.length > 0 ? (
                    profile.strengths.map((s) => (
                      <span key={s} className="badge badge-pass">
                        ✓ {s}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>None yet</span>
                  )}
                </div>
              </div>

              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Weak Areas (Not Started/Emerging):</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                  {profile.weak_areas?.length > 0 ? (
                    profile.weak_areas.map((w) => (
                      <span key={w} className="badge badge-fail">
                        ✗ {w}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>None</span>
                  )}
                </div>
              </div>

              {/* Quick Actions */}
              <div style={{ marginTop: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
                <label className="form-label">Record Progress</label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button className="btn btn-secondary btn-sm" onClick={handleSyncMastery} disabled={loading}>
                    📥 Sync Session Mastery
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={handleRecordLesson} disabled={loading}>
                    ✓ Complete Lesson
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={handleRecordAssessment} disabled={loading}>
                    📝 Record Score (85%)
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              No profile found for <code>{learnerId}</code>. Use the form on the left to initialize a profile.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
