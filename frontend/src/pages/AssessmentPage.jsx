import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';
import LoadingSpinner from '../components/LoadingSpinner';

export default function AssessmentPage() {
  const { session, updateSession } = useTestSession();

  // Section A: Question Generation
  const [questionType, setQuestionType] = useState('mcq');
  const [count, setCount] = useState(1);
  const [loadingGen, setLoadingGen] = useState(false);
  const [genError, setGenError] = useState(null);
  const [generatedQuestions, setGeneratedQuestions] = useState(session.generatedQuestions || []);

  // Section B: Answer Evaluation
  const [selectedQuestion, setSelectedQuestion] = useState(session.selectedQuestion || null);
  const [studentAnswerText, setStudentAnswerText] = useState('B');
  const [loadingEval, setLoadingEval] = useState(false);
  const [evalError, setEvalError] = useState(null);
  const [evalResult, setEvalResult] = useState(session.evaluationResult || null);

  // Section C: Misconception Detection
  const [loadingMisc, setLoadingMisc] = useState(false);
  const [miscError, setMiscError] = useState(null);
  const [miscResult, setMiscResult] = useState(session.misconceptionAnalysis || null);

  const activeConcept = session.selectedConcept || session.concepts?.[0] || {
    concept_id: 'cpt_variables',
    name: 'Variables and Storage',
    description: 'Named references storing values in memory',
    difficulty: 'beginner',
    learning_objectives: ['Define variable declarations and assignment'],
    prerequisite_concept_ids: [],
    related_concept_ids: [],
    source_chunk_ids: [],
  };

  const handleGenerateQuestions = async (e) => {
    e.preventDefault();
    setLoadingGen(true);
    setGenError(null);

    try {
      const qList = await api.generateQuestions({
        concept: activeConcept,
        question_type: questionType,
        count: Number(count),
        lesson_id: session.selectedLesson?.lesson_id || null,
      });

      setGeneratedQuestions(qList);
      if (qList && qList.length > 0) {
        setSelectedQuestion(qList[0]);
        if (qList[0].question_type === 'mcq' && qList[0].options?.length > 0) {
          setStudentAnswerText(qList[0].options[0]);
        } else {
          setStudentAnswerText('A variable stores data values in memory for program execution.');
        }
      }
      updateSession({
        generatedQuestions: qList,
        selectedQuestion: qList[0] || null,
      });
    } catch (err) {
      setGenError(err.message || 'Question generation failed');
    } finally {
      setLoadingGen(false);
    }
  };

  const handleEvaluateAnswer = async (e) => {
    e.preventDefault();
    if (!selectedQuestion) {
      setEvalError('Please generate or select a question first.');
      return;
    }

    setLoadingEval(true);
    setEvalError(null);

    const studentAnswerPayload = {
      question_id: selectedQuestion.question_id,
      answer_text: studentAnswerText,
      selected_option: selectedQuestion.question_type === 'mcq' ? studentAnswerText.charAt(0) : undefined,
    };

    try {
      const res = await api.evaluateAnswer({
        question: selectedQuestion,
        student_answer: studentAnswerPayload,
      });
      setEvalResult(res);
      updateSession({
        studentAnswer: studentAnswerPayload,
        evaluationResult: res,
      });
    } catch (err) {
      setEvalError(err.message || 'Answer evaluation failed');
    } finally {
      setLoadingEval(false);
    }
  };

  const handleDetectMisconceptions = async () => {
    if (!selectedQuestion || !evalResult) {
      setMiscError('Please evaluate an answer before running misconception detection.');
      return;
    }

    setLoadingMisc(true);
    setMiscError(null);

    try {
      const studentAnswerPayload = {
        question_id: selectedQuestion.question_id,
        answer_text: studentAnswerText,
        selected_option: selectedQuestion.question_type === 'mcq' ? studentAnswerText.charAt(0) : undefined,
      };

      const mRes = await api.detectMisconceptions({
        question: selectedQuestion,
        student_answer: studentAnswerPayload,
        evaluation_result: evalResult,
        concept: activeConcept,
        concept_graph: session.conceptGraph || null,
      });

      setMiscResult(mRes);
      updateSession({
        misconceptionAnalysis: mRes,
      });
    } catch (err) {
      setMiscError(err.message || 'Misconception detection failed');
    } finally {
      setLoadingMisc(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📝 Assessment Intelligence (Phase 5)</h1>
        <p className="page-description">
          Generate pedagogical questions, evaluate student submissions (deterministic MCQ & semantic open-ended), and diagnose conceptual misconceptions.
        </p>
      </div>

      {/* SECTION A: QUESTION GENERATION */}
      <div className="card">
        <div className="card-title">
          <span>Section A: Question Generation</span>
          <span className="badge badge-warning">DEVELOPER DIAGNOSTIC MODE</span>
        </div>

        <div style={{ marginBottom: '14px', fontSize: '13px' }}>
          Target Concept: <strong>{activeConcept.name}</strong> (
          <code style={{ color: '#38bdf8' }}>{activeConcept.concept_id}</code> | Difficulty: {activeConcept.difficulty})
        </div>

        {genError && (
          <div className="alert alert-error">
            <span>❌</span>
            <div>{genError}</div>
          </div>
        )}

        <form onSubmit={handleGenerateQuestions}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Question Type</label>
              <select
                className="form-select"
                value={questionType}
                onChange={(e) => setQuestionType(e.target.value)}
                disabled={loadingGen}
              >
                <option value="mcq">Multiple Choice (MCQ)</option>
                <option value="short_answer">Short Answer</option>
                <option value="conceptual">Conceptual</option>
                <option value="application">Application</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Batch Count (1 - 5)</label>
              <input
                type="number"
                className="form-input"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                min="1"
                max="5"
                disabled={loadingGen}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loadingGen} style={{ width: '100%' }}>
            {loadingGen ? (
              <LoadingSpinner size="sm" text="Generating Assessment Questions..." inline color="text-white" />
            ) : (
              '🎯 Generate Questions for Concept'
            )}
          </button>
        </form>
      </div>

      {/* GENERATED QUESTIONS LIST */}
      {generatedQuestions && generatedQuestions.length > 0 && (
        <div className="card">
          <div className="card-title">
            <span>Generated Questions ({generatedQuestions.length})</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {generatedQuestions.map((q, idx) => (
              <div
                key={q.question_id}
                style={{
                  padding: '16px',
                  background: selectedQuestion?.question_id === q.question_id ? 'var(--bg-card-alt)' : 'var(--bg-primary)',
                  border: selectedQuestion?.question_id === q.question_id ? '1px solid #38bdf8' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge badge-available">Q{idx + 1}</span>
                    <span className="phase-badge">{q.question_type}</span>
                    <span className="phase-badge">{q.difficulty}</span>
                  </div>

                  <button
                    className={`btn btn-sm ${selectedQuestion?.question_id === q.question_id ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => {
                      setSelectedQuestion(q);
                      updateSession({ selectedQuestion: q });
                      if (q.question_type === 'mcq' && q.options?.length > 0) {
                        setStudentAnswerText(q.options[0]);
                      }
                    }}
                  >
                    {selectedQuestion?.question_id === q.question_id ? '✓ Selected for Answering' : 'Select Question'}
                  </button>
                </div>

                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                  {q.question_text}
                </div>

                {q.options && q.options.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px', paddingLeft: '12px' }}>
                    {q.options.map((opt, oi) => (
                      <div key={oi} style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                        {opt}
                      </div>
                    ))}
                  </div>
                )}

                {/* Developer Diagnostic Info */}
                <div style={{ marginTop: '8px', padding: '10px', background: 'rgba(56, 189, 248, 0.05)', borderRadius: '4px', fontSize: '11px' }}>
                  <div style={{ color: '#38bdf8', fontWeight: 600 }}>[DEVELOPER ONLY DIAGNOSTICS]</div>
                  <div>Correct Answer: <strong>{q.correct_answer}</strong></div>
                  <div>Explanation: {q.explanation}</div>
                  <div>Learning Objective: {q.learning_objective}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION B: ANSWER EVALUATION */}
      {selectedQuestion && (
        <div className="card">
          <div className="card-title">
            <span>Section B: Answer Submission & Evaluation</span>
          </div>

          <div style={{ marginBottom: '14px', fontSize: '13px' }}>
            Evaluating Question: <strong>{selectedQuestion.question_text}</strong>
          </div>

          {evalError && (
            <div className="alert alert-error">
              <span>❌</span>
              <div>{evalError}</div>
            </div>
          )}

          <form onSubmit={handleEvaluateAnswer}>
            <div className="form-group">
              <label className="form-label">Student Answer / Option</label>
              {selectedQuestion.question_type === 'mcq' && selectedQuestion.options?.length > 0 ? (
                <select
                  className="form-select"
                  value={studentAnswerText}
                  onChange={(e) => setStudentAnswerText(e.target.value)}
                  disabled={loadingEval}
                >
                  {selectedQuestion.options.map((opt, oi) => (
                    <option key={oi} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <textarea
                  className="form-textarea"
                  value={studentAnswerText}
                  onChange={(e) => setStudentAnswerText(e.target.value)}
                  placeholder="Enter learner's open-ended response"
                  disabled={loadingEval}
                />
              )}
            </div>

            <button type="submit" className="btn btn-primary" disabled={loadingEval} style={{ width: '100%' }}>
              {loadingEval ? (
                <LoadingSpinner size="sm" text="Evaluating Answer..." inline color="text-white" />
              ) : (
                '⚖️ Evaluate Student Answer'
              )}
            </button>
          </form>

          {evalResult && (
            <div style={{ marginTop: '20px', padding: '16px', background: 'var(--bg-primary)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <strong style={{ fontSize: '14px' }}>Evaluation Result</strong>
                <span className={`badge ${evalResult.correctness ? 'badge-pass' : 'badge-fail'}`}>
                  Score: {(evalResult.score * 100).toFixed(0)}% | {evalResult.correctness ? 'CORRECT' : 'INCORRECT'}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                <div><span style={{ color: 'var(--text-secondary)' }}>Feedback:</span> {evalResult.feedback}</div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Evidence:</span> {evalResult.evidence}</div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Confidence:</span> {evalResult.confidence}</div>
              </div>

              <div style={{ marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleDetectMisconceptions}
                  disabled={loadingMisc}
                >
                  {loadingMisc ? (
                    <LoadingSpinner size="sm" text="Diagnosing Misconceptions..." inline color="text-slate-600" />
                  ) : (
                    '🔬 Run Misconception Detection'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SECTION C: MISCONCEPTION DETECTION */}
      {miscResult && (
        <div className="card">
          <div className="card-title">
            <span>Section C: Misconception Analysis</span>
            <span className={`badge ${miscResult.has_misconception ? 'badge-warning' : 'badge-pass'}`}>
              {miscResult.has_misconception ? 'Misconception Diagnosed' : 'No Misconception'}
            </span>
          </div>

          <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div><span style={{ color: 'var(--text-secondary)' }}>Summary:</span> {miscResult.summary}</div>
            <div>
              <span style={{ color: 'var(--text-secondary)' }}>Confidence:</span>{' '}
              {typeof miscResult.confidence === 'number' ? miscResult.confidence.toFixed(2) : 'N/A'}
            </div>

            {miscResult.misconceptions && miscResult.misconceptions.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <label className="form-label">Diagnosed Flaws</label>
                {miscResult.misconceptions.map((m, mi) => (
                  <div key={mi} style={{ padding: '12px', background: 'var(--bg-primary)', borderRadius: '6px', marginBottom: '8px', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span className="badge badge-warning">{m.severity} severity</span>
                      <strong>{m.description}</strong>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Remediation: {m.remediation_strategy}</div>
                    {m.prerequisite_concept_id && (
                      <div style={{ fontSize: '11px', color: '#f87171', marginTop: '2px' }}>
                        Prerequisite Gap: <code style={{ color: '#f87171' }}>{m.prerequisite_concept_id}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
