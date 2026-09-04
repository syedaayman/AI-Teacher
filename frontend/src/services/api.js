/**
 * AI Brain Centralized API Client
 * Authoritative integration layer between frontend dashboard and FastAPI backend.
 */

export function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    // Cleanly normalize: remove trailing slashes and redundant /api/v1 if present in .env
    return envUrl.trim().replace(/\/+$/, '').replace(/\/api\/v1$/, '');
  }

  // Fallback for browser execution (local or LAN access)
  if (typeof window !== 'undefined' && window.location) {
    const protocol = window.location.protocol || 'http:';
    const hostname = window.location.hostname || '127.0.0.1';
    return `${protocol}//${hostname}:8000`;
  }

  return 'http://127.0.0.1:8000';
}

const API_PREFIX = '/api/v1';

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
    id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    timestamp: new Date().toISOString(),
    ...entry,
  });
  if (apiLogs.length > 100) apiLogs.pop();
  logListeners.forEach((cb) => cb(getApiLogs()));
}

/**
 * Robust HTTP request wrapper with rich diagnostic telemetry.
 */
async function request(endpoint, options = {}) {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullPath = cleanEndpoint.startsWith(API_PREFIX) ? cleanEndpoint : `${API_PREFIX}${cleanEndpoint}`;
  const url = `${baseUrl}${fullPath}`;
  const method = (options.method || 'GET').toUpperCase();
  const headers = { ...options.headers };
  let body = options.body;

  // Track request data for debug inspector
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
      endpoint: cleanEndpoint,
      fullPath,
      url,
      requestPayload: loggedRequestBody,
      responseStatus: response.status,
      responsePayload: data,
      durationMs,
      ok: response.ok,
      errorDetails: !response.ok ? (typeof data === 'object' ? data : { raw: data }) : null,
    });

    if (!response.ok) {
      let detailMsg = '';
      if (typeof data === 'object' && data !== null) {
        if (data.detail) {
          detailMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail, null, 2);
        } else if (data.error && data.error.message) {
          detailMsg = data.error.message;
        } else {
          detailMsg = JSON.stringify(data, null, 2);
        }
      } else {
        detailMsg = String(data);
      }

      const formattedErrorMsg = `${method} ${url}\nStatus: ${response.status} (${response.statusText})\nResponse:\n${detailMsg}`;
      const err = new Error(formattedErrorMsg);
      err.status = response.status;
      err.statusText = response.statusText;
      err.url = url;
      err.method = method;
      err.data = data;
      err.shortMessage = detailMsg || `HTTP ${response.status}: ${response.statusText}`;
      throw err;
    }

    return data;
  } catch (err) {
    if (!err.status) {
      // Network, DNS, Connection Refused, or CORS failure
      const durationMs = Date.now() - startTime;
      const errorMsg = err.message || 'Network request failed';
      const diagnosis = [
        `Unable to reach backend at: ${url}`,
        `Potential causes:`,
        `1. FastAPI backend is not running.`,
        `2. Backend is bound to 127.0.0.1 instead of 0.0.0.0 for LAN access.`,
        `3. Port 8000 is blocked or unreachable.`,
        `4. CORS preflight failed for origin ${typeof window !== 'undefined' ? window.location.origin : 'unknown'}.`,
      ].join('\n');

      const fullDiagnosticMsg = `${method} ${url}\nNetwork/Fetch Error: ${errorMsg}\n\n${diagnosis}`;

      addLogEntry({
        method,
        endpoint: cleanEndpoint,
        fullPath,
        url,
        requestPayload: loggedRequestBody,
        responseStatus: 0,
        responsePayload: {
          error: errorMsg,
          diagnosis,
        },
        durationMs,
        ok: false,
        errorDetails: { message: errorMsg, diagnosis },
      });

      const networkErr = new Error(fullDiagnosticMsg);
      networkErr.status = 0;
      networkErr.url = url;
      networkErr.method = method;
      networkErr.isNetworkError = true;
      networkErr.shortMessage = `Network/Fetch Error: ${errorMsg} (${url})`;
      throw networkErr;
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
