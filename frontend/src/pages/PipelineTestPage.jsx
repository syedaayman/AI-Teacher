import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';

export default function PipelineTestPage() {
  const { session, updateSession } = useTestSession();

  // Step Statuses: 'NOT RUN' | 'RUNNING' | 'PASS' | 'FAIL' | 'BLOCKED'
  const [statuses, setStatuses] = useState({
    step1: 'PASS',
    step2: 'NOT RUN',
    step3: 'NOT RUN',
    step4: 'NOT RUN',
    step5: 'NOT RUN',
    step6: 'NOT RUN',
    step7: 'NOT RUN',
    step8: 'NOT RUN',
    step9: 'NOT RUN',
    step10: 'NOT RUN',
    step11: 'NOT RUN',
    step12: 'NOT RUN',
  });

  const [stepData, setStepData] = useState({});
  const [stepErrors, setStepErrors] = useState({});
  const [topicInput, setTopicInput] = useState('Data Structures and Algorithms in Python');
  const [isRunningAll, setIsRunningAll] = useState(false);

  const setStatus = (stepKey, status, data = null, error = null) => {
    setStatuses((prev) => ({ ...prev, [stepKey]: status }));
    if (data !== null) setStepData((prev) => ({ ...prev, [stepKey]: data }));
    if (error !== null) setStepErrors((prev) => ({ ...prev, [stepKey]: error }));
  };

  // STEP 2: Material Processing (or synthesize text material if no file uploaded)
  const runStep2 = async () => {
    setStatus('step2', 'RUNNING');
    try {
      let doc = session.materialDocument;
      if (!doc) {
        // Create sample text document to test real Phase 2 endpoint
        const blob = new Blob(
          [
            `Binary Search Trees and Algorithmic Complexity.\n\nA binary search tree (BST) maintains the invariant that left children are smaller than parent, and right children are larger.\n\nSearching takes O(log n) time in balanced trees and O(n) in degenerate trees.\n\nTree traversals include in-order, pre-order, and post-order.`
          ],
          { type: 'text/plain' }
        );
        const file = new File([blob], 'pipeline_sample_material.txt', { type: 'text/plain' });
        const formData = new FormData();
        formData.append('file', file);
        formData.append('chunk_size', 500);
        formData.append('chunk_overlap', 50);
        formData.append('auto_ingest', true);

        const res = await api.processMaterial(formData);
        doc = res.extracted_document;
        updateSession({
          materialDocument: doc,
          materialId: doc.material_id,
          materialFilename: doc.filename,
        });
      }
      setStatus('step2', 'PASS', {
        filename: doc.filename,
        material_id: doc.material_id,
        chunks_count: doc.chunks?.length || 0,
      });
      return doc;
    } catch (err) {
      setStatus('step2', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 3: RAG Retrieval & Context
  const runStep3 = async () => {
    if (!session.materialId && !stepData.step2) {
      setStatus('step3', 'BLOCKED', null, 'Prerequisite: Run Step 2 first.');
      return;
    }
    setStatus('step3', 'RUNNING');
    try {
      const searchRes = await api.searchRAG({
        query: 'What is binary search tree complexity and traversal?',
        top_k: 3,
        material_id: session.materialId,
      });
      const ctxRes = await api.getContextRAG({
        query: 'What is binary search tree complexity and traversal?',
        top_k: 3,
        material_id: session.materialId,
      });

      updateSession({
        ragResults: searchRes.results,
        groundedContext: ctxRes,
      });

      setStatus('step3', 'PASS', {
        retrieved_chunks: searchRes.results.length,
        citations: ctxRes.citations?.length || 0,
      });
      return { searchRes, ctxRes };
    } catch (err) {
      setStatus('step3', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 4: Concept Extraction & Graph Validation
  const runStep4 = async () => {
    setStatus('step4', 'RUNNING');
    try {
      let concepts;
      if (session.materialDocument) {
        concepts = await api.extractConcepts({
          document: session.materialDocument,
          material_id: session.materialId,
        });
      } else {
        concepts = await api.extractConcepts({
          topic: topicInput,
        });
      }

      const gRes = await api.buildConceptGraph(concepts);

      updateSession({
        concepts,
        conceptGraph: gRes.graph,
        topologicalOrder: gRes.topological_order,
        selectedConcept: concepts[0],
      });

      setStatus('step4', 'PASS', {
        concepts_count: concepts.length,
        topological_order: gRes.topological_order.map((c) => c.name).join(' → '),
      });
      return { concepts, graph: gRes.graph };
    } catch (err) {
      setStatus('step4', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 5: Lesson Planning & Syllabus Generation
  const runStep5 = async () => {
    setStatus('step5', 'RUNNING');
    try {
      let syllabus;
      if (session.materialDocument) {
        syllabus = await api.planLessons({
          document: session.materialDocument,
          title: 'Algorithmic Data Structures Course',
        });
      } else {
        syllabus = await api.planLessons({
          topic: topicInput,
          title: 'Algorithmic Data Structures Course',
        });
      }

      updateSession({
        syllabus,
        selectedLesson: syllabus.lessons?.[0] || null,
      });

      setStatus('step5', 'PASS', {
        syllabus_id: syllabus.syllabus_id,
        lessons_count: syllabus.lessons?.length || 0,
        lesson_titles: syllabus.lessons?.map((l) => l.title).join(', '),
      });
      return syllabus;
    } catch (err) {
      setStatus('step5', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 6: Question Generation
  const runStep6 = async () => {
    const targetConcept = session.selectedConcept || session.concepts?.[0];
    if (!targetConcept) {
      setStatus('step6', 'BLOCKED', null, 'Prerequisite: Run Step 4 first.');
      return;
    }

    setStatus('step6', 'RUNNING');
    try {
      const qList = await api.generateQuestions({
        concept: targetConcept,
        question_type: 'mcq',
        count: 1,
        lesson_id: session.selectedLesson?.lesson_id || null,
      });

      const q = qList[0];
      updateSession({
        generatedQuestions: qList,
        selectedQuestion: q,
      });

      setStatus('step6', 'PASS', {
        question_id: q.question_id,
        question_text: q.question_text,
        correct_answer: q.correct_answer,
      });
      return q;
    } catch (err) {
      setStatus('step6', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 7: Student Answer Preparation
  const runStep7 = () => {
    const q = session.selectedQuestion;
    if (!q) {
      setStatus('step7', 'BLOCKED', null, 'Prerequisite: Run Step 6 first.');
      return;
    }

    const answerPayload = {
      question_id: q.question_id,
      answer_text: q.options?.[0] || q.correct_answer || 'Balanced binary search tree searching is O(log n).',
      selected_option: q.question_type === 'mcq' && q.options?.length > 0 ? q.options[0].charAt(0) : undefined,
    };

    updateSession({ studentAnswer: answerPayload });
    setStatus('step7', 'PASS', {
      submitted_answer: answerPayload.answer_text,
    });
    return answerPayload;
  };

  // STEP 8: Answer Evaluation
  const runStep8 = async () => {
    const q = session.selectedQuestion;
    const ans = session.studentAnswer;
    if (!q || !ans) {
      setStatus('step8', 'BLOCKED', null, 'Prerequisite: Complete Step 6 and Step 7.');
      return;
    }

    setStatus('step8', 'RUNNING');
    try {
      const evalRes = await api.evaluateAnswer({
        question: q,
        student_answer: ans,
      });

      updateSession({ evaluationResult: evalRes });
      setStatus('step8', 'PASS', {
        score: evalRes.score,
        correctness: evalRes.correctness,
        feedback: evalRes.feedback,
      });
      return evalRes;
    } catch (err) {
      setStatus('step8', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 9: Misconception Detection
  const runStep9 = async () => {
    const q = session.selectedQuestion;
    const ans = session.studentAnswer;
    const evalRes = session.evaluationResult;
    const concept = session.selectedConcept || session.concepts?.[0];

    if (!q || !ans || !evalRes || !concept) {
      setStatus('step9', 'BLOCKED', null, 'Prerequisite: Complete Steps 6, 7, and 8.');
      return;
    }

    setStatus('step9', 'RUNNING');
    try {
      const mRes = await api.detectMisconceptions({
        question: q,
        student_answer: ans,
        evaluation_result: evalRes,
        concept,
        concept_graph: session.conceptGraph || null,
      });

      updateSession({ misconceptionAnalysis: mRes });
      setStatus('step9', 'PASS', {
        has_misconception: mRes.has_misconception,
        summary: mRes.summary,
      });
      return mRes;
    } catch (err) {
      setStatus('step9', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 10: Mastery Update
  const runStep10 = async () => {
    const evalRes = session.evaluationResult;
    const concept = session.selectedConcept || session.concepts?.[0];

    if (!evalRes || !concept) {
      setStatus('step10', 'BLOCKED', null, 'Prerequisite: Run Step 8 first.');
      return;
    }

    setStatus('step10', 'RUNNING');
    try {
      const updatedMastery = await api.updateMastery({
        concept_id: concept.concept_id,
        evaluation_result: evalRes,
        previous_mastery: session.conceptMastery || undefined,
      });

      updateSession({ conceptMastery: updatedMastery });
      setStatus('step10', 'PASS', {
        mastery_score: updatedMastery.mastery_score,
        mastery_level: updatedMastery.mastery_level,
        attempts: updatedMastery.attempts,
      });
      return updatedMastery;
    } catch (err) {
      setStatus('step10', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 11: Adaptive Decision
  const runStep11 = async () => {
    const concept = session.selectedConcept || session.concepts?.[0];
    const evalRes = session.evaluationResult;
    const mastery = session.conceptMastery;

    if (!concept || !evalRes || !mastery) {
      setStatus('step11', 'BLOCKED', null, 'Prerequisite: Complete Steps 8 and 10.');
      return;
    }

    setStatus('step11', 'RUNNING');
    try {
      const decision = await api.decideAdaptiveAction({
        current_concept_id: concept.concept_id,
        current_difficulty: 'beginner',
        evaluation_result: evalRes,
        concept_mastery: mastery,
        misconception_analysis: session.misconceptionAnalysis || null,
        concept_graph: session.conceptGraph || null,
        learner_id: session.learnerId,
        session_id: 'pipeline_session_01',
      });

      updateSession({ adaptationDecision: decision });
      setStatus('step11', 'PASS', {
        action: decision.action,
        target_concept_id: decision.target_concept_id,
        target_difficulty: decision.target_difficulty,
        reason: decision.reason,
      });
      return decision;
    } catch (err) {
      setStatus('step11', 'FAIL', null, err.message);
      throw err;
    }
  };

  // STEP 12: Learner Profile Update
  const runStep12 = async () => {
    const mastery = session.conceptMastery;
    const evalRes = session.evaluationResult;

    if (!mastery) {
      setStatus('step12', 'BLOCKED', null, 'Prerequisite: Run Step 10 first.');
      return;
    }

    setStatus('step12', 'RUNNING');
    try {
      // 1. Ensure profile exists
      let p;
      try {
        p = await api.getProfile(session.learnerId);
      } catch {
        p = await api.createProfile({
          learner_id: session.learnerId,
          name: 'Pipeline Test Learner',
          preferred_language: 'english',
          learning_goal: 'Pipeline Verification',
          preferred_difficulty: 'beginner',
          total_lessons: 5,
        });
      }

      // 2. Sync Mastery
      p = await api.updateProfileMastery({
        learner_id: session.learnerId,
        concept_mastery: mastery,
      });

      // 3. Record assessment
      if (evalRes) {
        p = await api.recordAssessmentResult({
          learner_id: session.learnerId,
          score: evalRes.score,
        });
      }

      updateSession({ learnerProfile: p });
      setStatus('step12', 'PASS', {
        overall_mastery: p.overall_mastery,
        strengths: p.strengths.join(', ') || 'None',
        average_score: p.average_score,
      });
      return p;
    } catch (err) {
      setStatus('step12', 'FAIL', null, err.message);
      throw err;
    }
  };

  // Run all steps sequentially
  const handleRunAll = async () => {
    setIsRunningAll(true);
    try {
      await runStep2();
      await runStep3();
      await runStep4();
      await runStep5();
      await runStep6();
      runStep7();
      await runStep8();
      await runStep9();
      await runStep10();
      await runStep11();
      await runStep12();
    } catch (err) {
      console.error('Pipeline execution stopped due to failure:', err);
    } finally {
      setIsRunningAll(false);
    }
  };

  const getBadgeClass = (status) => {
    switch (status) {
      case 'PASS':
        return 'badge-pass';
      case 'FAIL':
        return 'badge-fail';
      case 'RUNNING':
        return 'badge-running';
      case 'BLOCKED':
        return 'badge-blocked';
      default:
        return 'badge-not-run';
    }
  };

  const STEPS = [
    { key: 'step1', title: 'STEP 1: Input Topic / Material', fn: null, desc: 'Define input curriculum topic or uploaded document' },
    { key: 'step2', title: 'STEP 2: Material Processing (Phase 2)', fn: runStep2, desc: 'POST /api/v1/materials/process — Ingestion, text cleaning & chunking' },
    { key: 'step3', title: 'STEP 3: RAG Retrieval & Grounding (Phase 3)', fn: runStep3, desc: 'POST /api/v1/rag/search & /rag/context — Semantic retrieval & citations' },
    { key: 'step4', title: 'STEP 4: Concept Extraction & Graph (Phase 4)', fn: runStep4, desc: 'POST /api/v1/concepts/extract & /concepts/graph — DFS cycle validation' },
    { key: 'step5', title: 'STEP 5: Lesson Planning & Syllabus (Phase 4)', fn: runStep5, desc: 'POST /api/v1/lessons/plan — Pedagogical lesson sequencing' },
    { key: 'step6', title: 'STEP 6: Question Generation (Phase 5)', fn: runStep6, desc: 'POST /api/v1/assessment/generate-questions — MCQ/Open question generation' },
    { key: 'step7', title: 'STEP 7: Student Answer Preparation', fn: runStep7, desc: 'Prepare student submission answer for evaluation' },
    { key: 'step8', title: 'STEP 8: Answer Evaluation (Phase 5)', fn: runStep8, desc: 'POST /api/v1/assessment/evaluate-answer — Deterministic & semantic scoring' },
    { key: 'step9', title: 'STEP 9: Misconception Detection (Phase 5)', fn: runStep9, desc: 'POST /api/v1/assessment/detect-misconceptions — Prerequisite gap diagnosis' },
    { key: 'step10', title: 'STEP 10: Mastery Calculation (Phase 6)', fn: runStep10, desc: 'POST /api/v1/adaptive/mastery/update — 0.6*prev + 0.4*score calculation' },
    { key: 'step11', title: 'STEP 11: Adaptive Decision Engine (Phase 6)', fn: runStep11, desc: 'POST /api/v1/adaptive/decide — 6-tier pedagogical decision hierarchy' },
    { key: 'step12', title: 'STEP 12: Learner Profile Sync (Phase 7)', fn: runStep12, desc: 'POST /api/v1/learner-profile/update-mastery — Strength/weakness sync' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🚀 Guided End-to-End Pipeline</h1>
        <p className="page-description">
          Step-by-step verification of the entire AI Brain backend (Phases 1–7) through real HTTP API calls.
        </p>
      </div>

      <div className="card">
        <div className="card-title">
          <span>Pipeline Controls</span>
          <button className="btn btn-primary btn-sm" onClick={handleRunAll} disabled={isRunningAll}>
            {isRunningAll ? '⏳ Executing Pipeline...' : '▶ Run All Steps (1 → 12)'}
          </button>
        </div>

        <div className="form-group">
          <label className="form-label">Active Topic</label>
          <input
            type="text"
            className="form-input"
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            disabled={isRunningAll}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {STEPS.map((step) => {
          const status = statuses[step.key];
          const data = stepData[step.key];
          const err = stepErrors[step.key];

          return (
            <div key={step.key} className="pipeline-step-card">
              <div className="pipeline-step-header">
                <div className="pipeline-step-title">
                  <span>{step.title}</span>
                  <span className={`badge ${getBadgeClass(status)}`}>{status}</span>
                </div>

                {step.fn && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={step.fn}
                    disabled={status === 'RUNNING' || isRunningAll}
                  >
                    {status === 'RUNNING' ? 'Running...' : 'Run Step'}
                  </button>
                )}
              </div>

              <div className="pipeline-step-body">{step.desc}</div>

              {err && (
                <div className="alert alert-error" style={{ marginTop: '10px', marginBottom: '0' }}>
                  <span>❌</span>
                  <div>{err}</div>
                </div>
              )}

              {data && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '10px 12px',
                    background: 'var(--bg-primary)',
                    borderRadius: '4px',
                    fontSize: '12px',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#38bdf8', marginBottom: '4px' }}>✓ Output Data:</div>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '11px' }}>
                    {JSON.stringify(data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
