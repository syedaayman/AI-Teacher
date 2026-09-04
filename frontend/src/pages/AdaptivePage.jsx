import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function AdaptivePage() {
  const { session, updateSession } = useTestSession();

  // Inputs
  const [conceptId, setConceptId] = useState(
    session.selectedConcept?.concept_id || session.concepts?.[0]?.concept_id || 'cpt_variables'
  );
  const [currentDifficulty, setCurrentDifficulty] = useState('beginner');
  const [evalScore, setEvalScore] = useState(session.evaluationResult?.score ?? 0.9);
  const [isCorrect, setIsCorrect] = useState(session.evaluationResult?.correctness ?? true);
  const [hasPrereqMisconception, setHasPrereqMisconception] = useState(false);
  const [prereqConceptId, setPrereqConceptId] = useState('cpt_prereq_basics');
  const [hasConceptualMisconception, setHasConceptualMisconception] = useState(false);

  // States
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [masteryResult, setMasteryResult] = useState(session.conceptMastery || null);
  const [decisionResult, setDecisionResult] = useState(session.adaptationDecision || null);

  const handleRunAdaptation = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const qId = session.selectedQuestion?.question_id || `qst_sim_${Date.now()}`;
      // 1. Construct valid EvaluationResult matching backend schema
      const evaluationResult = {
        evaluation_id: session.evaluationResult?.evaluation_id || `eval_${Date.now()}`,
        question_id: qId,
        concept_id: conceptId,
        correctness: isCorrect,
        score: Number(evalScore),
        confidence: 0.95,
        expected_answer: 'Reference correct answer formulation',
        student_answer: 'Learner submitted answer',
        concepts_tested: [conceptId],
        concepts_demonstrated: isCorrect ? [conceptId] : [],
        concepts_missing: !isCorrect ? [conceptId] : [],
        evidence: isCorrect ? 'Demonstrated clear conceptual understanding' : 'Struggled with core principle',
        feedback: isCorrect ? 'Excellent job!' : 'Needs targeted conceptual review',
      };

      // 2. Construct valid MisconceptionAnalysis matching backend schema if enabled
      let misconceptionAnalysis = null;
      if (hasPrereqMisconception) {
        misconceptionAnalysis = {
          detected: true,
          overall_confidence: 0.9,
          summary: 'Prerequisite gap detected in foundational concept',
          misconceptions: [
            {
              misconception_id: `misc_prereq_${Date.now()}`,
              concept_id: conceptId,
              description: 'Missing foundational concept required for current topic',
              evidence: 'Failed to demonstrate prerequisite understanding',
              severity: 'high',
              confidence: 0.9,
              affected_concept_ids: [prereqConceptId],
              source_question_id: qId,
              recommended_focus: 'Review prerequisite material',
            },
          ],
        };
      } else if (hasConceptualMisconception) {
        misconceptionAnalysis = {
          detected: true,
          overall_confidence: 0.85,
          summary: 'Direct conceptual confusion in current concept',
          misconceptions: [
            {
              misconception_id: `misc_cpt_${Date.now()}`,
              concept_id: conceptId,
              description: 'Confusing assignment with equality comparison',
              evidence: 'Used assignment operator when comparison was expected',
              severity: 'medium',
              confidence: 0.85,
              affected_concept_ids: [conceptId],
              source_question_id: qId,
              recommended_focus: 'Clarify assignment vs comparison operator semantics',
            },
          ],
        };
      }

      // 3. Update Mastery via MasteryEngine (Phase 6)
      const updatedMastery = await api.updateMastery({
        concept_id: conceptId,
        evaluation_result: evaluationResult,
        previous_mastery: masteryResult || undefined,
      });
      setMasteryResult(updatedMastery);

      // 4. Derive Next Pedagogical Action via AdaptiveEngine (Phase 6)
      const decision = await api.decideAdaptiveAction({
        current_concept_id: conceptId,
        current_difficulty: currentDifficulty,
        evaluation_result: evaluationResult,
        concept_mastery: updatedMastery,
        misconception_analysis: misconceptionAnalysis,
        concept_graph: session.conceptGraph || null,
        learner_id: session.learnerId || 'dev_learner_01',
        session_id: 'session_dev_01',
      });

      setDecisionResult(decision);

      updateSession({
        conceptMastery: updatedMastery,
        adaptationDecision: decision,
      });
    } catch (err) {
      setError(err.formattedMessage || err.message || 'Adaptive simulation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">⚙️ Adaptive Learning Engine (Phase 6)</h1>
        <p className="page-description">
          Deterministic mastery updating (0.6 × previous + 0.4 × current) and 6-tier pedagogical decision engine.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '12px' }}>{error}</pre>
          </div>
        </div>
      )}

      <div className="grid-2">
        {/* SIMULATION CONTROLS */}
        <div className="card">
          <div className="card-title">
            <span>Simulate Learner Attempt</span>
          </div>

          <form onSubmit={handleRunAdaptation}>
            <div className="form-group">
              <label className="form-label">Concept ID</label>
              <input
                type="text"
                className="form-input"
                value={conceptId}
                onChange={(e) => setConceptId(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Current Difficulty</label>
                <select
                  className="form-select"
                  value={currentDifficulty}
                  onChange={(e) => setCurrentDifficulty(e.target.value)}
                  disabled={loading}
                >
                  <option value="beginner">beginner</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Evaluation Score (0.0 - 1.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0.0"
                  max="1.0"
                  className="form-input"
                  value={evalScore}
                  onChange={(e) => {
                    const sc = Number(e.target.value);
                    setEvalScore(sc);
                    setIsCorrect(sc >= 0.7);
                  }}
                  disabled={loading}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Misconception Simulation</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={hasPrereqMisconception}
                    onChange={(e) => {
                      setHasPrereqMisconception(e.target.checked);
                      if (e.target.checked) setHasConceptualMisconception(false);
                    }}
                    disabled={loading}
                  />
                  Priority 1: Simulate Prerequisite Gap (triggers review_prerequisite)
                </label>

                {hasPrereqMisconception && (
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Prerequisite Concept ID"
                    value={prereqConceptId}
                    onChange={(e) => setPrereqConceptId(e.target.value)}
                    style={{ marginLeft: '22px', width: 'calc(100% - 22px)' }}
                  />
                )}

                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={hasConceptualMisconception}
                    onChange={(e) => {
                      setHasConceptualMisconception(e.target.checked);
                      if (e.target.checked) setHasPrereqMisconception(false);
                    }}
                    disabled={loading}
                  />
                  Priority 2: Simulate Conceptual Misconception (triggers remediate_misconception)
                </label>
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', marginTop: '8px' }}>
              {loading ? '⚙️ Running Adaptation...' : '🚀 Run Adaptation Pipeline'}
            </button>
          </form>
        </div>

        {/* MASTERY STATE */}
        <div className="card">
          <div className="card-title">
            <span>Concept Mastery State (MasteryEngine)</span>
            {masteryResult && (
              <span className="badge badge-pass">{masteryResult.mastery_level?.toUpperCase()}</span>
            )}
          </div>

          {masteryResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Mastery Score:</span>{' '}
                <strong style={{ fontSize: '16px', color: '#38bdf8' }}>
                  {(masteryResult.mastery_score * 100).toFixed(1)}%
                </strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Mastery Level:</span>{' '}
                <span className="phase-badge">{masteryResult.mastery_level}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Total Attempts:</span> {masteryResult.attempts}
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Attempt Breakdown:</span>{' '}
                <span style={{ color: '#34d399' }}>✓ {masteryResult.correct_attempts}</span> |{' '}
                <span style={{ color: '#f87171' }}>✗ {masteryResult.incorrect_attempts}</span> |{' '}
                <span style={{ color: '#fbbf24' }}>~ {masteryResult.partial_attempts}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Consecutive Correct / Failures:</span>{' '}
                {masteryResult.consecutive_correct} / {masteryResult.consecutive_failures}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Formula: First attempt = score | Subsequent = 0.6 * prev + 0.4 * score
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              No mastery record computed yet. Click "Run Adaptation Pipeline" to calculate.
            </div>
          )}
        </div>
      </div>

      {/* ADAPTATION DECISION PROMINENT DISPLAY */}
      {decisionResult && (
        <div className="card" style={{ border: '2px solid #3b82f6', background: 'rgba(59, 130, 246, 0.05)' }}>
          <div className="card-title">
            <span style={{ color: '#60a5fa', fontSize: '16px' }}>🎯 Next Pedagogical Action (AdaptationDecision)</span>
            <span className="badge badge-available">ID: {decisionResult.decision_id}</span>
          </div>

          <div className="grid-3" style={{ marginBottom: '16px' }}>
            <div style={{ padding: '12px', background: 'var(--bg-card)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Action</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>
                {decisionResult.action}
              </div>
            </div>

            <div style={{ padding: '12px', background: 'var(--bg-card)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Target Concept</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                {decisionResult.target_concept_id}
              </div>
            </div>

            <div style={{ padding: '12px', background: 'var(--bg-card)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Target Difficulty</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                {decisionResult.target_difficulty}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
            <div>
              <span style={{ color: 'var(--text-secondary)' }}>Reason:</span>{' '}
              <strong>{decisionResult.reason}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-secondary)' }}>Evidence Trail:</span>{' '}
              <span style={{ color: 'var(--text-muted)' }}>{decisionResult.evidence}</span>
            </div>
            {decisionResult.misconception_ids?.length > 0 && (
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Associated Misconceptions:</span>{' '}
                {decisionResult.misconception_ids.join(', ')}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
