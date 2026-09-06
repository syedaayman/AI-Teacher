const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

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

  // 9. Teaching Sessions (Core Adaptive Teaching Loop)
  /**
   * Start an adaptive teaching session calibrated to time budget and instructional depth.
   * @param {Object} params
   * @param {string} params.learner_id - Unique learner ID
   * @param {string} [params.topic] - Topic to teach if no material uploaded
   * @param {string} [params.material_id] - Uploaded material ID for grounded teaching
   * @param {string} [params.lesson_id] - Specific lesson ID from syllabus
   * @param {string[]} [params.concept_ids] - Specific sequence of concepts
   * @param {number} [params.available_time_minutes=20] - Available session duration (1-180)
   * @param {string} [params.desired_depth='standard'] - 'quick_overview', 'standard', or 'deep_dive'
   * @param {string} [params.preferred_language] - 'english', 'hindi', or 'hinglish'
   * @param {string} [params.preferred_difficulty] - 'beginner', 'intermediate', or 'advanced'
   * @returns {Promise<Object>} SessionStepResponse
   */
  startSession: ({
    learner_id,
    topic = null,
    material_id = null,
    lesson_id = null,
    concept_ids = null,
    available_time_minutes = 20,
    desired_depth = 'standard',
    preferred_language = null,
    preferred_difficulty = null,
  }) => {
    const body = { learner_id, available_time_minutes, desired_depth };
    if (topic) body.topic = topic;
    if (material_id) body.material_id = material_id;
    if (lesson_id) body.lesson_id = lesson_id;
    if (concept_ids) body.concept_ids = concept_ids;
    if (preferred_language) body.preferred_language = preferred_language;
    if (preferred_difficulty) body.preferred_difficulty = preferred_difficulty;

    return request('/sessions/start', {
      method: 'POST',
      body,
    });
  },

  /**
   * Advance to the next instructional step (Explain -> Demonstrate -> Question).
   * @param {Object} params
   * @param {string} params.session_id - Active session ID
   * @param {string} params.learner_id - Learner ID
   * @returns {Promise<Object>} SessionStepResponse
   */
  advanceStep: ({ session_id, learner_id }) =>
    request('/sessions/advance', {
      method: 'POST',
      body: { session_id, learner_id },
    }),

  /**
   * Submit student answer to the current assessment question.
   * @param {Object} params
   * @param {string} params.session_id - Active session ID
   * @param {string} params.learner_id - Learner ID submitting answer
   * @param {string} params.question_id - Question ID being answered
   * @param {string} [params.answer_text] - Free-text answer
   * @param {string} [params.selected_option] - Selected option string for MCQ
   * @param {string} [params.reasoning] - Optional student reasoning context
   * @returns {Promise<Object>} SessionStepResponse
   */
  submitSessionAnswer: ({
    session_id,
    learner_id,
    question_id,
    answer_text = null,
    selected_option = null,
    reasoning = null,
  }) =>
    request('/sessions/submit-answer', {
      method: 'POST',
      body: {
        session_id,
        learner_id,
        question_id,
        answer_text,
        selected_option,
        reasoning,
      },
    }),

  /**
   * Switch instructional language mid-session (English, Hindi, Hinglish).
   * @param {Object} params
   * @param {string} params.session_id - Active session ID
   * @param {string} params.language - 'english', 'hindi', or 'hinglish'
   * @returns {Promise<Object>} SessionStepResponse
   */
  switchSessionLanguage: ({ session_id, language }) =>
    request('/sessions/switch-language', {
      method: 'POST',
      body: { session_id, language },
    }),

  /**
   * Fetch active session state (with transparent DB recovery if cache was cleared).
   * @param {string} session_id
   * @returns {Promise<Object>} LessonSessionState
   */
  getSessionState: (session_id) =>
    request(`/sessions/${encodeURIComponent(session_id)}`),

  /**
   * Conclude or abandon an active teaching session.
   * @param {string} session_id
   * @param {string} [final_status='completed'] - 'completed', 'abandoned', or 'paused'
   * @returns {Promise<Object>} LessonSessionState
   */
  endSession: (session_id, final_status = 'completed') =>
    request(
      `/sessions/${encodeURIComponent(session_id)}/end?final_status=${encodeURIComponent(final_status)}`,
      { method: 'POST' }
    ),

  // 10. Comprehensive Final Assessment & Diagnostics
  /**
   * Generate a multi-concept final exam package.
   * @param {Object} payload - FinalAssessmentRequest matching backend schema
   * @param {string} payload.learner_id
   * @param {string} [payload.lesson_id]
   * @param {string} [payload.session_id]
   * @param {string[]} [payload.concept_ids]
   * @param {number} [payload.num_questions=5]
   * @param {string} [payload.difficulty='intermediate']
   * @param {string} [payload.language='english']
   * @returns {Promise<Object>} FinalAssessmentPackage
   */
  generateFinalAssessment: (payload) =>
    request('/assessment/final/generate', {
      method: 'POST',
      body: payload,
    }),

  /**
   * Submit exam answers for grading and diagnostic report generation.
   * @param {Object} payload - FinalAssessmentSubmission matching backend schema
   * @param {string} payload.assessment_id
   * @param {string} payload.learner_id
   * @param {string} [payload.session_id]
   * @param {string} [payload.lesson_id]
   * @param {Array<{ question_id: string, answer_text?: string, selected_option?: string, reasoning?: string }>} payload.answers
   * @param {string} [payload.language='english']
   * @returns {Promise<Object>} AssessmentReport
   */
  evaluateFinalAssessment: (payload) =>
    request('/assessment/final/evaluate', {
      method: 'POST',
      body: payload,
    }),

  // 11. Long-Term Learning Memory & Spaced Repetition (SuperMemo SM-2)
  /**
   * Get prioritized spaced repetition review queue based on memory decay curves.
   * @param {string} learner_id
   * @param {Object} [params]
   * @param {number} [params.max_items=10]
   * @param {number} [params.retention_threshold=0.85]
   * @returns {Promise<Object>} ReviewQueue
   */
  getReviewQueue: (learner_id, { max_items = 10, retention_threshold = 0.85 } = {}) => {
    const validId = (learner_id && String(learner_id).trim()) || 'default_learner';
    return request(
      `/memory/${encodeURIComponent(validId)}/queue?max_items=${max_items}&retention_threshold=${retention_threshold}`
    );
  },

  /**
   * Record concept review score and update SM-2 retention parameters.
   * @param {string} learner_id
   * @param {Object} params
   * @param {string} params.concept_id
   * @param {number} params.score - 0.0 to 1.0
   * @returns {Promise<Object>} MemoryUpdateResult
   */
  updateMemory: (learner_id, { concept_id, score }) => {
    const validId = (learner_id && String(learner_id).trim()) || 'default_learner';
    return request(`/memory/${encodeURIComponent(validId)}/update`, {
      method: 'POST',
      body: { concept_id, score },
    });
  },

  /**
   * Get longitudinal learning memory, session retention, and mastery analytics.
   * @param {string} learner_id
   * @returns {Promise<Object>} Historical learning summary dictionary
   */
  getMemorySummary: (learner_id) => {
    const validId = (learner_id && String(learner_id).trim()) || 'default_learner';
    return request(`/memory/${encodeURIComponent(validId)}/summary`);
  },

  // 12. AI Teaching Video Generation (Sections 7 & 8)
  /**
   * Check status of video generation providers (local canvas vs external HeyGen/D-ID).
   */
  getVideoProviders: () => request('/video/providers'),

  /**
   * Plan progressive video scenes for a lesson concept.
   */
  planVideoScenes: (payload) =>
    request('/video/plan-scenes', {
      method: 'POST',
      body: payload,
    }),

  /**
   * Generate video manifest / trigger video pipeline.
   */
  generateLessonVideo: (payload) =>
    request('/video/generate', {
      method: 'POST',
      body: payload,
    }),

  // 13. Personalized 7-Day Plan (Section 21)
  /**
   * Generate 7-day spaced curriculum and revision schedule.
   */
  getSevenDayPlan: (payload) =>
    request('/lessons/seven-day-plan', {
      method: 'POST',
      body: payload,
    }),
};

export default api;
