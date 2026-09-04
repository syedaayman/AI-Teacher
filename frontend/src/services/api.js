const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// In-memory log buffer of API transactions for developer inspection
const apiLogs = [];
const logListeners = new Set();

export function getApiLogs() {
  return [...apiLogs];
}

export function subscribeToApiLogs(listener) {
  logListeners.add(listener);
  return () => logListeners.delete(listener);
}

function addLogEntry(entry) {
  apiLogs.unshift({
    id: `log_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
    timestamp: new Date().toISOString(),
    ...entry,
  });
  if (apiLogs.length > 100) apiLogs.pop();
  logListeners.forEach((cb) => cb(getApiLogs()));
}

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const method = options.method || 'GET';
  const headers = { ...options.headers };
  let body = options.body;

  // Track raw request data for debug inspector
  let loggedRequestBody = null;

  if (body && !(body instanceof FormData) && typeof body === 'object') {
    headers['Content-Type'] = 'application/json';
    loggedRequestBody = body;
    body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    loggedRequestBody = '[FormData payload]';
  }

  const startTime = Date.now();
  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
    });

    let data;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    const durationMs = Date.now() - startTime;

    addLogEntry({
      method,
      endpoint,
      url,
      requestPayload: loggedRequestBody,
      responseStatus: response.status,
      responsePayload: data,
      durationMs,
      ok: response.ok,
    });

    if (!response.ok) {
      const errorMsg =
        typeof data === 'object' && data?.detail
          ? typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail)
          : `HTTP ${response.status}: ${response.statusText}`;
      const err = new Error(errorMsg);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    return data;
  } catch (err) {
    if (!err.status) {
      // Network/CORS failure
      addLogEntry({
        method,
        endpoint,
        url,
        requestPayload: loggedRequestBody,
        responseStatus: 0,
        responsePayload: { error: err.message || 'Network request failed' },
        durationMs: Date.now() - startTime,
        ok: false,
      });
    }
    throw err;
  }
}

export const api = {
  // 1. Health
  getHealth: () => request('/health'),

  // 2. Materials
  processMaterial: (formData) =>
    request('/materials/process', {
      method: 'POST',
      body: formData,
    }),

  // 3. RAG
  searchRAG: ({ query, top_k = 5, material_id = null }) =>
    request('/rag/search', {
      method: 'POST',
      body: { query, top_k, material_id },
    }),
  getContextRAG: ({ query, top_k = 5, material_id = null }) =>
    request('/rag/context', {
      method: 'POST',
      body: { query, top_k, material_id },
    }),
  getStatsRAG: () => request('/rag/stats'),

  // 4. Concepts
  extractConcepts: ({ topic = null, document = null, material_id = null }) =>
    request('/concepts/extract', {
      method: 'POST',
      body: { topic, document, material_id },
    }),
  buildConceptGraph: (concepts) =>
    request('/concepts/graph', {
      method: 'POST',
      body: { concepts },
    }),

  // 5. Lessons
  planLessons: ({ topic = null, document = null, title = null }) =>
    request('/lessons/plan', {
      method: 'POST',
      body: { topic, document, title },
    }),

  // 6. Assessment
  generateQuestions: ({ concept, question_type = 'mcq', count = 1, lesson_id = null }) =>
    request('/assessment/generate-questions', {
      method: 'POST',
      body: { concept, question_type, count, lesson_id },
    }),
  evaluateAnswer: ({ question, student_answer }) =>
    request('/assessment/evaluate-answer', {
      method: 'POST',
      body: { question, student_answer },
    }),
  detectMisconceptions: ({ question, student_answer, evaluation_result, concept, concept_graph = null }) =>
    request('/assessment/detect-misconceptions', {
      method: 'POST',
      body: { question, student_answer, evaluation_result, concept, concept_graph },
    }),

  // 7. Adaptive Engine
  updateMastery: ({ concept_id, evaluation_result, previous_mastery = null }) =>
    request('/adaptive/mastery/update', {
      method: 'POST',
      body: { concept_id, evaluation_result, previous_mastery },
    }),
  decideAdaptiveAction: ({
    current_concept_id,
    current_difficulty,
    evaluation_result,
    concept_mastery,
    misconception_analysis = null,
    concept_graph = null,
    learner_id = null,
    session_id = null,
  }) =>
    request('/adaptive/decide', {
      method: 'POST',
      body: {
        current_concept_id,
        current_difficulty,
        evaluation_result,
        concept_mastery,
        misconception_analysis,
        concept_graph,
        learner_id,
        session_id,
      },
    }),

  // 8. Learner Profile
  createProfile: (profileData) =>
    request('/learner-profile/create', {
      method: 'POST',
      body: profileData,
    }),
  getProfile: (learner_id) => request(`/learner-profile/${encodeURIComponent(learner_id)}`),
  updatePreferences: ({ learner_id, preferred_language = null, preferred_difficulty = null, learning_goal = null }) =>
    request('/learner-profile/update-preferences', {
      method: 'POST',
      body: { learner_id, preferred_language, preferred_difficulty, learning_goal },
    }),
  updateProfileMastery: ({ learner_id, concept_mastery }) =>
    request('/learner-profile/update-mastery', {
      method: 'POST',
      body: { learner_id, concept_mastery },
    }),
  recordLessonCompletion: ({ learner_id, lesson_id }) =>
    request('/learner-profile/record-lesson', {
      method: 'POST',
      body: { learner_id, lesson_id },
    }),
  recordAssessmentResult: ({ learner_id, score }) =>
    request('/learner-profile/record-assessment', {
      method: 'POST',
      body: { learner_id, score },
    }),
};
