import React, { useState, useEffect } from 'react';
import { getApiLogs, subscribeToApiLogs } from '../services/api';

const API_CONTRACTS = [
  {
    method: 'GET',
    path: '/api/v1/health',
    desc: 'Check backend connectivity and version info',
    req: 'None',
    res: 'HealthResponse { status, service, version, timestamp }',
  },
  {
    method: 'POST',
    path: '/api/v1/materials/process',
    desc: 'Upload document (PDF/DOCX/PPTX/TXT), clean text, chunk, and index into ChromaDB',
    req: 'multipart/form-data: file, chunk_size, chunk_overlap, auto_ingest',
    res: 'MaterialProcessingResponse { extracted_document, ingestion_result }',
  },
  {
    method: 'POST',
    path: '/api/v1/rag/search',
    desc: 'Semantic retrieval across indexed document chunks with vector embeddings',
    req: 'RAGSearchRequest { query: str, top_k: int, material_id: Optional[str] }',
    res: 'RAGSearchResponse { query, results: List[RetrievedChunk] }',
  },
  {
    method: 'POST',
    path: '/api/v1/rag/context',
    desc: 'Build grounded teacher prompt context with source reference citations',
    req: 'RAGContextRequest { query: str, top_k: int, material_id: Optional[str] }',
    res: 'GroundedContext { query, formatted_context, citations }',
  },
  {
    method: 'POST',
    path: '/api/v1/concepts/extract',
    desc: 'Extract pedagogical concepts from topic or grounded material chunks',
    req: 'ConceptExtractionRequest { topic?: str, document?: ExtractedDocument, material_id?: str }',
    res: 'List[Concept]',
  },
  {
    method: 'POST',
    path: '/api/v1/concepts/graph',
    desc: 'Validate prerequisite acyclicity (DFS) and compute topological sort sequence',
    req: 'ConceptGraphRequest { concepts: List[Concept] }',
    res: 'ConceptGraphResponse { graph: ConceptGraph, topological_order: List[Concept] }',
  },
  {
    method: 'POST',
    path: '/api/v1/lessons/plan',
    desc: 'Generate sequenced syllabus and structured lessons from material or topic',
    req: 'LessonPlanRequest { topic?: str, document?: ExtractedDocument, title?: str }',
    res: 'Syllabus { syllabus_id, title, total_lessons, lessons: List[Lesson] }',
  },
  {
    method: 'POST',
    path: '/api/v1/assessment/generate-questions',
    desc: 'Generate MCQ, short answer, conceptual, or application questions for a concept',
    req: 'QuestionGenerationRequest { concept: Concept, question_type: str, count: int, lesson_id?: str }',
    res: 'List[Question]',
  },
  {
    method: 'POST',
    path: '/api/v1/assessment/evaluate-answer',
    desc: 'Evaluate student answer (deterministic MCQ / semantic open-ended LLM)',
    req: 'AnswerEvaluationRequest { question: Question, student_answer: StudentAnswer }',
    res: 'EvaluationResult { evaluation_id, score, correctness, feedback, evidence, confidence }',
  },
  {
    method: 'POST',
    path: '/api/v1/assessment/detect-misconceptions',
    desc: 'Diagnose genuine conceptual or prerequisite flaws from student answers',
    req: 'MisconceptionDetectionRequest { question, student_answer, evaluation_result, concept, concept_graph? }',
    res: 'MisconceptionAnalysis { analysis_id, has_misconception, summary, misconceptions: List[Misconception] }',
  },
  {
    method: 'POST',
    path: '/api/v1/adaptive/mastery/update',
    desc: 'Deterministically calculate concept mastery (0.6*prev + 0.4*score)',
    req: 'MasteryUpdateRequest { concept_id: str, evaluation_result: EvaluationResult, previous_mastery?: ConceptMastery }',
    res: 'ConceptMastery { concept_id, mastery_score, mastery_level, attempts, correct_attempts, ... }',
  },
  {
    method: 'POST',
    path: '/api/v1/adaptive/decide',
    desc: 'Evaluate performance, mastery, prerequisites, and misconceptions for next pedagogical action',
    req: 'AdaptiveDecisionRequest { current_concept_id, current_difficulty, evaluation_result, concept_mastery, ... }',
    res: 'AdaptationDecision { decision_id, action, target_concept_id, target_difficulty, reason, evidence }',
  },
  {
    method: 'POST',
    path: '/api/v1/learner-profile/create',
    desc: 'Initialize and store structured learner profile',
    req: 'CreateProfileRequest { learner_id, name?, preferred_language, learning_goal?, preferred_difficulty, total_lessons }',
    res: 'LearnerProfile { learner_id, name, preferred_language, concept_masteries, strengths, weak_areas, ... }',
  },
  {
    method: 'GET',
    path: '/api/v1/learner-profile/{learner_id}',
    desc: 'Retrieve existing learner profile and summary statistics',
    req: 'None (path param)',
    res: 'LearnerProfile',
  },
];

export default function RawJsonPage() {
  const [logs, setLogs] = useState(getApiLogs());
  const [selectedLogId, setSelectedLogId] = useState(logs[0]?.id || null);
  const [copiedType, setCopiedType] = useState(null);

  useEffect(() => {
    const unsub = subscribeToApiLogs((updatedLogs) => {
      setLogs(updatedLogs);
      if (!selectedLogId && updatedLogs.length > 0) {
        setSelectedLogId(updatedLogs[0].id);
      }
    });
    return unsub;
  }, [selectedLogId]);

  const selectedLog = logs.find((l) => l.id === selectedLogId) || logs[0];

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(typeof text === 'object' ? JSON.stringify(text, null, 2) : String(text));
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📊 Raw API Inspector & Contracts</h1>
        <p className="page-description">
          Inspect raw JSON request and response payloads exchanged between the dashboard and FastAPI.
        </p>
      </div>

      <div className="grid-2">
        {/* LOG LIST */}
        <div className="card">
          <div className="card-title">
            <span>Recent API Calls ({logs.length})</span>
          </div>

          <div style={{ maxHeight: '480px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                No API calls captured yet. Perform actions across dashboard pages to record transactions.
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  onClick={() => setSelectedLogId(log.id)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: selectedLog?.id === log.id ? 'var(--bg-card-alt)' : 'var(--bg-primary)',
                    border: selectedLog?.id === log.id ? '1px solid #38bdf8' : '1px solid var(--border-color)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`phase-badge ${log.method === 'GET' ? 'badge-available' : 'badge-pass'}`}>
                      {log.method}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>{log.endpoint}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className={`badge ${log.ok ? 'badge-pass' : 'badge-fail'}`}>
                      {log.responseStatus || 'ERR'}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{log.durationMs}ms</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* SELECTED PAYLOAD DETAILS */}
        {selectedLog ? (
          <div className="card">
            <div className="card-title">
              <span>Payload Inspector</span>
              <span className="badge badge-available">
                {selectedLog.method} {selectedLog.endpoint}
              </span>
            </div>

            <div style={{ marginBottom: '14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              Status: <strong>{selectedLog.responseStatus}</strong> | Duration: <strong>{selectedLog.durationMs}ms</strong> | Time:{' '}
              {new Date(selectedLog.timestamp).toLocaleTimeString()}
            </div>

            {/* REQUEST */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span className="form-label" style={{ margin: 0 }}>
                  REQUEST BODY
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleCopy(selectedLog.requestPayload, 'req')}
                >
                  {copiedType === 'req' ? '✓ Copied!' : '📋 Copy Request'}
                </button>
              </div>
              <div className="code-block" style={{ maxHeight: '180px' }}>
                {selectedLog.requestPayload
                  ? JSON.stringify(selectedLog.requestPayload, null, 2)
                  : '[No request body]'}
              </div>
            </div>

            {/* RESPONSE */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span className="form-label" style={{ margin: 0 }}>
                  RESPONSE BODY
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleCopy(selectedLog.responsePayload, 'res')}
                >
                  {copiedType === 'res' ? '✓ Copied!' : '📋 Copy Response'}
                </button>
              </div>
              <div className="code-block" style={{ maxHeight: '200px' }}>
                {JSON.stringify(selectedLog.responsePayload, null, 2)}
              </div>
            </div>
          </div>
        ) : (
          <div className="card">
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Select an API call to inspect payloads.</div>
          </div>
        )}
      </div>

      {/* API CONTRACTS TABLE */}
      <div className="card" style={{ marginTop: '20px' }}>
        <div className="card-title">
          <span>Implemented API Contracts (Phase 1–7 Thin Adapters)</span>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Method</th>
                <th>Endpoint</th>
                <th>Description</th>
                <th>Request Model</th>
                <th>Response Model</th>
              </tr>
            </thead>
            <tbody>
              {API_CONTRACTS.map((contract, idx) => (
                <tr key={idx}>
                  <td>
                    <span className="phase-badge">{contract.method}</span>
                  </td>
                  <td>
                    <code style={{ fontSize: '11px', color: '#38bdf8' }}>{contract.path}</code>
                  </td>
                  <td>{contract.desc}</td>
                  <td>
                    <code style={{ fontSize: '11px', color: '#94a3b8' }}>{contract.req}</code>
                  </td>
                  <td>
                    <code style={{ fontSize: '11px', color: '#34d399' }}>{contract.res}</code>
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
