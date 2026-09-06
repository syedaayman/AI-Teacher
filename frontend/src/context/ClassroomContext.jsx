import React, { createContext, useContext, useReducer, useCallback } from 'react';
import api from '../services/api';

/**
 * @typedef {Object} InstructionalDelivery
 * @property {'explain'|'demonstrate'} step
 * @property {string} concept_id
 * @property {string} concept_name
 * @property {string} title
 * @property {string} content
 * @property {string} [visual_description]
 * @property {boolean} diagram_required
 * @property {string} [code_snippet]
 * @property {string[]} key_takeaways
 * @property {string} [analogy]
 * @property {string} [real_world_application]
 * @property {string} [counter_example]
 * @property {'english'|'hindi'|'hinglish'} language
 * @property {'beginner'|'intermediate'|'advanced'} difficulty
 * @property {Array<Object>} sources
 */

/**
 * @typedef {Object} ClassroomState
 */
const initialClassroomState = {
  // Session Identity
  sessionId: '',
  learnerId: '',
  materialId: null,
  topic: null,
  lessonId: null,

  // Lesson Configuration
  availableTimeMinutes: 20,
  desiredDepth: 'standard',
  preferredDifficulty: 'intermediate',
  language: 'english',

  // Session Status
  status: 'idle', // 'idle' | 'active' | 'completed' | 'paused' | 'abandoned'
  currentStep: 'understand', // 'understand' | 'plan' | 'explain' | 'demonstrate' | 'question' | 'evaluate' | 'adapt' | 'complete'
  stepCount: 0,
  completed: false,
  finalStatus: null,

  // Concept Progress & Learning Journey
  currentConceptId: null,
  currentConceptName: null,
  conceptIndex: 0,
  totalConcepts: 0,
  concepts: [],
  conceptNames: {},

  // AI Teacher Emotional & Interaction State: 'idle' | 'speaking' | 'thinking' | 'listening' | 'encouraging'
  teacherState: 'idle',

  // Time
  remainingTimeMinutes: 20,

  // Pedagogical Delivery & Interaction
  delivery: null,
  question: null,
  evaluation: null,
  misconceptionAnalysis: null,
  adaptation: null,
  message: '',

  // Operational Lifecycle & Network Flags
  phase: 'INITIAL', // 'INITIAL' | 'STARTING' | 'ACTIVE' | 'ADVANCING' | 'QUESTION' | 'SUBMITTING' | 'EVALUATED' | 'ADAPTED' | 'LANGUAGE_SWITCHING' | 'COMPLETED' | 'ERROR'
  loading: false,
  starting: false,
  advancing: false,
  submitting: false,
  switchingLanguage: false,
  ending: false,
  recovering: false,
  error: null,
  errorDetails: null,

  // Raw Backend Response Cache
  lastResponse: null,

  // Final Assessment & Diagnostic Report (M2-6)
  assessmentPackage: null,
  assessmentReport: null,
};

// --------------------------------------------------------------------
// Action Types
// --------------------------------------------------------------------
const ACTIONS = {
  START_REQUEST: 'START_REQUEST',
  START_SUCCESS: 'START_SUCCESS',
  START_FAILURE: 'START_FAILURE',

  ADVANCE_REQUEST: 'ADVANCE_REQUEST',
  ADVANCE_SUCCESS: 'ADVANCE_SUCCESS',
  ADVANCE_FAILURE: 'ADVANCE_FAILURE',

  SUBMIT_REQUEST: 'SUBMIT_REQUEST',
  SUBMIT_SUCCESS: 'SUBMIT_SUCCESS',
  SUBMIT_FAILURE: 'SUBMIT_FAILURE',

  LANGUAGE_SWITCH_REQUEST: 'LANGUAGE_SWITCH_REQUEST',
  LANGUAGE_SWITCH_SUCCESS: 'LANGUAGE_SWITCH_SUCCESS',
  LANGUAGE_SWITCH_FAILURE: 'LANGUAGE_SWITCH_FAILURE',

  RECOVERY_REQUEST: 'RECOVERY_REQUEST',
  RECOVERY_SUCCESS: 'RECOVERY_SUCCESS',
  RECOVERY_FAILURE: 'RECOVERY_FAILURE',

  END_REQUEST: 'END_REQUEST',
  END_SUCCESS: 'END_SUCCESS',
  END_FAILURE: 'END_FAILURE',

  RESET: 'RESET',
  CLEAR_ERROR: 'CLEAR_ERROR',
  CLEAR_EVALUATION: 'CLEAR_EVALUATION',
  SET_ASSESSMENT_PACKAGE: 'SET_ASSESSMENT_PACKAGE',
  SET_ASSESSMENT_REPORT: 'SET_ASSESSMENT_REPORT',
  HYDRATE_CONCEPTS: 'HYDRATE_CONCEPTS',
  SET_TEACHER_STATE: 'SET_TEACHER_STATE',
};

// Helper: Save active session metadata to localStorage
function saveSessionToStorage(sessionData) {
  if (sessionData && sessionData.sessionId && sessionData.status === 'active') {
    try {
      localStorage.setItem(
        'ai_teacher_active_session',
        JSON.stringify({
          sessionId: sessionData.sessionId,
          learnerId: sessionData.learnerId,
          topic: sessionData.topic,
          currentConceptName: sessionData.currentConceptName,
          conceptIndex: sessionData.conceptIndex,
          totalConcepts: sessionData.totalConcepts,
          remainingTimeMinutes: sessionData.remainingTimeMinutes,
          language: sessionData.language,
          savedAt: Date.now(),
        })
      );
    } catch {
      // ignore
    }
  } else if (sessionData && sessionData.completed) {
    try {
      localStorage.removeItem('ai_teacher_active_session');
    } catch {
      // ignore
    }
  }
}

// --------------------------------------------------------------------
// Normalization Helper
// --------------------------------------------------------------------
function applyStepResponse(state, response, overrides = {}) {
  const isComplete =
    response.status === 'completed' || response.current_step === 'complete';

  // Determine state phase
  let phase = 'ACTIVE';
  let defaultTeacherState = 'idle';

  if (isComplete) {
    phase = 'COMPLETED';
    defaultTeacherState = 'encouraging';
  } else if (response.evaluation) {
    phase = 'EVALUATED';
    defaultTeacherState =
      response.evaluation.correctness || (response.evaluation.score && response.evaluation.score >= 0.7)
        ? 'encouraging'
        : 'thinking';
  } else if (response.adaptation) {
    phase = 'ADAPTED';
    defaultTeacherState = 'thinking';
  } else if (response.current_step === 'question' || response.question) {
    phase = 'QUESTION';
    defaultTeacherState = 'listening';
  } else if (response.delivery) {
    defaultTeacherState = 'speaking';
  }

  const updatedState = {
    ...state,
    ...overrides,
    sessionId: response.session_id || state.sessionId,
    learnerId: response.learner_id || state.learnerId,
    currentStep: response.current_step || state.currentStep,
    status: response.status || state.status,
    currentConceptId: response.current_concept_id || state.currentConceptId,
    currentConceptName: response.current_concept_name || state.currentConceptName,
    conceptIndex: response.concept_index ?? state.conceptIndex,
    totalConcepts: response.total_concepts ?? state.totalConcepts,
    preferredDifficulty: response.difficulty || state.preferredDifficulty,
    language: response.language || state.language,
    remainingTimeMinutes:
      response.remaining_time_minutes ?? state.remainingTimeMinutes,
    stepCount: response.step_count ?? state.stepCount,

    // AI Teacher State
    teacherState: defaultTeacherState,

    // Pedagogical payloads
    delivery: response.delivery !== undefined ? response.delivery : state.delivery,
    question: response.question !== undefined ? response.question : null,
    evaluation: response.evaluation !== undefined ? response.evaluation : null,
    misconceptionAnalysis:
      response.misconception_analysis !== undefined
        ? response.misconception_analysis
        : null,
    adaptation:
      response.adaptation !== undefined ? response.adaptation : null,
    message: response.message || '',

    // Completion flags
    completed: isComplete,
    finalStatus: isComplete ? response.status || 'completed' : state.finalStatus,

    // Operational flags
    phase,
    loading: false,
    starting: false,
    advancing: false,
    submitting: false,
    switchingLanguage: false,
    ending: false,
    recovering: false,
    error: null,
    errorDetails: null,

    // Store raw response
    lastResponse: response,
  };

  saveSessionToStorage(updatedState);
  return updatedState;
}

// --------------------------------------------------------------------
// Reducer
// --------------------------------------------------------------------
function classroomReducer(state, action) {
  switch (action.type) {
    // --- Start Session ---
    case ACTIONS.START_REQUEST:
      return {
        ...initialClassroomState,
        learnerId: action.payload.learner_id || state.learnerId,
        topic: action.payload.topic || null,
        materialId: action.payload.material_id || null,
        lessonId: action.payload.lesson_id || null,
        availableTimeMinutes:
          action.payload.available_time_minutes || state.availableTimeMinutes,
        desiredDepth: action.payload.desired_depth || state.desiredDepth,
        preferredDifficulty:
          action.payload.preferred_difficulty || state.preferredDifficulty,
        language: action.payload.preferred_language || state.language,
        phase: 'STARTING',
        loading: true,
        starting: true,
        error: null,
        errorDetails: null,
      };

    case ACTIONS.START_SUCCESS:
      return applyStepResponse(state, action.payload.response, {
        topic: action.payload.config.topic || state.topic,
        materialId: action.payload.config.material_id || state.materialId,
        lessonId: action.payload.config.lesson_id || state.lessonId,
        availableTimeMinutes:
          action.payload.config.available_time_minutes || state.availableTimeMinutes,
        desiredDepth: action.payload.config.desired_depth || state.desiredDepth,
      });

    case ACTIONS.START_FAILURE:
      return {
        ...state,
        phase: 'ERROR',
        loading: false,
        starting: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- Advance Step ---
    case ACTIONS.ADVANCE_REQUEST:
      return {
        ...state,
        phase: 'ADVANCING',
        loading: true,
        advancing: true,
        error: null,
      };

    case ACTIONS.ADVANCE_SUCCESS:
      return applyStepResponse(state, action.payload);

    case ACTIONS.ADVANCE_FAILURE:
      return {
        ...state,
        phase: 'ERROR',
        loading: false,
        advancing: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- Submit Answer ---
    case ACTIONS.SUBMIT_REQUEST:
      return {
        ...state,
        phase: 'SUBMITTING',
        loading: true,
        submitting: true,
        error: null,
      };

    case ACTIONS.SUBMIT_SUCCESS:
      return applyStepResponse(state, action.payload);

    case ACTIONS.SUBMIT_FAILURE:
      return {
        ...state,
        phase: 'ERROR',
        loading: false,
        submitting: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- Switch Language ---
    case ACTIONS.LANGUAGE_SWITCH_REQUEST:
      return {
        ...state,
        phase: 'LANGUAGE_SWITCHING',
        loading: true,
        switchingLanguage: true,
        error: null,
      };

    case ACTIONS.LANGUAGE_SWITCH_SUCCESS:
      return applyStepResponse(state, action.payload);

    case ACTIONS.LANGUAGE_SWITCH_FAILURE:
      return {
        ...state,
        phase: 'ERROR',
        loading: false,
        switchingLanguage: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- Session Recovery ---
    case ACTIONS.RECOVERY_REQUEST:
      return {
        ...state,
        loading: true,
        recovering: true,
        error: null,
      };

    case ACTIONS.RECOVERY_SUCCESS: {
      const recovered = action.payload;
      const recoveredState = {
        ...state,
        sessionId: recovered.session_id,
        learnerId: recovered.learner_id,
        topic: recovered.topic || state.topic,
        materialId: recovered.material_id || state.materialId,
        lessonId: recovered.lesson_id || state.lessonId,
        currentStep: recovered.current_step,
        status: recovered.status,
        concepts: recovered.concepts || state.concepts || [],
        conceptNames: recovered.concept_names || state.conceptNames || {},
        currentConceptId:
          recovered.concepts?.[recovered.current_concept_index] || state.currentConceptId,
        currentConceptName:
          recovered.concept_names?.[
            recovered.concepts?.[recovered.current_concept_index]
          ] || state.currentConceptName,
        conceptIndex: recovered.current_concept_index ?? state.conceptIndex,
        totalConcepts: recovered.concepts ? recovered.concepts.length : state.totalConcepts,
        preferredDifficulty: recovered.difficulty || state.preferredDifficulty,
        language: recovered.language || state.language,
        availableTimeMinutes:
          recovered.time_budget_minutes ?? state.availableTimeMinutes,
        remainingTimeMinutes:
          recovered.remaining_time_minutes ?? state.remainingTimeMinutes,
        desiredDepth: recovered.desired_depth || state.desiredDepth,
        stepCount: recovered.step_count ?? state.stepCount,
        delivery: recovered.current_delivery || null,
        question: recovered.last_question || null,
        evaluation: recovered.last_evaluation || null,
        misconceptionAnalysis: recovered.last_misconception_analysis || null,
        adaptation: recovered.last_adaptation || null,
        completed: recovered.status === 'completed',
        finalStatus:
          recovered.status === 'completed' ? 'completed' : state.finalStatus,
        phase: recovered.status === 'completed' ? 'COMPLETED' : 'ACTIVE',
        teacherState: recovered.status === 'completed' ? 'encouraging' : 'idle',
        loading: false,
        recovering: false,
        error: null,
        errorDetails: null,
        lastResponse: recovered,
      };
      saveSessionToStorage(recoveredState);
      return recoveredState;
    }

    case ACTIONS.RECOVERY_FAILURE:
      return {
        ...state,
        loading: false,
        recovering: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- End Session ---
    case ACTIONS.END_REQUEST:
      return {
        ...state,
        loading: true,
        ending: true,
        error: null,
      };

    case ACTIONS.END_SUCCESS: {
      const endedState = {
        ...state,
        status: action.payload.status || 'completed',
        currentStep: action.payload.current_step || 'complete',
        completed: true,
        finalStatus: action.payload.status || 'completed',
        phase: 'COMPLETED',
        teacherState: 'encouraging',
        loading: false,
        ending: false,
        error: null,
      };
      saveSessionToStorage(endedState);
      return endedState;
    }

    case ACTIONS.END_FAILURE:
      return {
        ...state,
        loading: false,
        ending: false,
        error: action.payload.message,
        errorDetails: action.payload.details,
      };

    // --- Reset & Clear ---
    case ACTIONS.RESET:
      try {
        localStorage.removeItem('ai_teacher_active_session');
      } catch {
        // ignore
      }
      return { ...initialClassroomState };

    case ACTIONS.CLEAR_ERROR:
      return { ...state, error: null, errorDetails: null };

    case ACTIONS.CLEAR_EVALUATION:
      return {
        ...state,
        evaluation: null,
        misconceptionAnalysis: null,
        adaptation: null,
        phase: state.question ? 'QUESTION' : state.status === 'completed' ? 'COMPLETED' : 'ACTIVE',
        teacherState: state.question ? 'listening' : 'idle',
      };

    case ACTIONS.SET_ASSESSMENT_PACKAGE:
      return {
        ...state,
        assessmentPackage: action.payload,
      };

    case ACTIONS.SET_ASSESSMENT_REPORT:
      return {
        ...state,
        assessmentReport: action.payload,
      };

    case ACTIONS.HYDRATE_CONCEPTS:
      return {
        ...state,
        concepts: action.payload.concepts || state.concepts,
        conceptNames: action.payload.conceptNames || state.conceptNames,
      };

    case ACTIONS.SET_TEACHER_STATE:
      return {
        ...state,
        teacherState: action.payload || 'idle',
      };

    default:
      return state;
  }
}

// --------------------------------------------------------------------
// Context & Provider
// --------------------------------------------------------------------
const ClassroomContext = createContext(null);

export function ClassroomProvider({ children }) {
  const [state, dispatch] = useReducer(classroomReducer, initialClassroomState);

  /**
   * Start a continuous teaching session through Member 1 Teacher Agent.
   */
  const startClassroomSession = useCallback(
    async (config) => {
      if (state.starting || state.loading) return;

      dispatch({ type: ACTIONS.START_REQUEST, payload: config });
      try {
        const response = await api.startSession({
          learner_id: config.learner_id,
          topic: config.topic || null,
          material_id: config.material_id || null,
          lesson_id: config.lesson_id || null,
          concept_ids: config.concept_ids || null,
          available_time_minutes: config.available_time_minutes || 20,
          desired_depth: config.desired_depth || 'standard',
          preferred_language: config.preferred_language || null,
          preferred_difficulty: config.preferred_difficulty || null,
        });
        dispatch({
          type: ACTIONS.START_SUCCESS,
          payload: { response, config },
        });

        // Hydrate ordered concepts & concept_names from backend session state
        if (response.session_id) {
          api.getSessionState(response.session_id).then((fullSession) => {
            if (fullSession && fullSession.concepts && fullSession.concepts.length > 0) {
              dispatch({
                type: ACTIONS.HYDRATE_CONCEPTS,
                payload: {
                  concepts: fullSession.concepts,
                  conceptNames: fullSession.concept_names || {},
                },
              });
            }
          }).catch((err) => {
            console.debug('Could not pre-hydrate concept graph:', err);
          });
        }

        return response;
      } catch (err) {
        dispatch({
          type: ACTIONS.START_FAILURE,
          payload: { message: err.message, details: err.data },
        });
        throw err;
      }
    },
    [state.starting, state.loading]
  );

  /**
   * Advance the teaching loop to the next instructional phase.
   */
  const advanceTeachingStep = useCallback(async () => {
    if (!state.sessionId) {
      throw new Error('Cannot advance step: no active session found.');
    }
    if (state.advancing || state.loading) return;

    dispatch({ type: ACTIONS.ADVANCE_REQUEST });
    try {
      const response = await api.advanceStep({
        session_id: state.sessionId,
        learner_id: state.learnerId,
      });
      dispatch({ type: ACTIONS.ADVANCE_SUCCESS, payload: response });
      return response;
    } catch (err) {
      dispatch({
        type: ACTIONS.ADVANCE_FAILURE,
        payload: { message: err.message, details: err.data },
      });
      throw err;
    }
  }, [state.sessionId, state.learnerId, state.advancing, state.loading]);

  /**
   * Submit student's answer to the currently active check question.
   */
  const submitAnswer = useCallback(
    async (payload) => {
      if (!state.sessionId) {
        throw new Error('Cannot submit answer: no active session found.');
      }
      if (state.submitting || state.loading) return;

      const qId = payload.question_id || state.question?.question_id;
      if (!qId) {
        throw new Error('Cannot submit answer: missing question identifier.');
      }

      dispatch({ type: ACTIONS.SUBMIT_REQUEST });
      try {
        const response = await api.submitSessionAnswer({
          session_id: state.sessionId,
          learner_id: state.learnerId,
          question_id: qId,
          answer_text: payload.answer_text || null,
          selected_option: payload.selected_option || null,
          reasoning: payload.reasoning || null,
        });
        dispatch({ type: ACTIONS.SUBMIT_SUCCESS, payload: response });
        return response;
      } catch (err) {
        dispatch({
          type: ACTIONS.SUBMIT_FAILURE,
          payload: { message: err.message, details: err.data },
        });
        throw err;
      }
    },
    [state.sessionId, state.learnerId, state.question, state.submitting, state.loading]
  );

  /**
   * Switch the instructional language mid-session.
   */
  const switchLanguage = useCallback(
    async (newLanguage) => {
      if (!state.sessionId) {
        throw new Error('Cannot switch language: no active session found.');
      }
      if (state.switchingLanguage || state.loading) return;

      dispatch({ type: ACTIONS.LANGUAGE_SWITCH_REQUEST });
      try {
        const response = await api.switchSessionLanguage({
          session_id: state.sessionId,
          language: newLanguage,
        });
        dispatch({ type: ACTIONS.LANGUAGE_SWITCH_SUCCESS, payload: response });
        return response;
      } catch (err) {
        dispatch({
          type: ACTIONS.LANGUAGE_SWITCH_FAILURE,
          payload: { message: err.message, details: err.data },
        });
        throw err;
      }
    },
    [state.sessionId, state.switchingLanguage, state.loading]
  );

  /**
   * Refresh or recover session state from database.
   */
  const refreshSession = useCallback(
    async (sid) => {
      const targetId = sid || state.sessionId;
      if (!targetId) {
        throw new Error('Cannot refresh session: no session ID provided.');
      }
      if (state.recovering || state.loading) return;

      dispatch({ type: ACTIONS.RECOVERY_REQUEST });
      try {
        const stateData = await api.getSessionState(targetId);
        dispatch({ type: ACTIONS.RECOVERY_SUCCESS, payload: stateData });
        return stateData;
      } catch (err) {
        dispatch({
          type: ACTIONS.RECOVERY_FAILURE,
          payload: { message: err.message, details: err.data },
        });
        throw err;
      }
    },
    [state.sessionId, state.recovering, state.loading]
  );

  /**
   * Conclude or abandon an active teaching session.
   */
  const endClassroomSession = useCallback(
    async (finalStatus = 'completed') => {
      if (!state.sessionId) return;
      if (state.ending || state.loading) return;

      dispatch({ type: ACTIONS.END_REQUEST });
      try {
        const stateData = await api.endSession(state.sessionId, finalStatus);
        dispatch({ type: ACTIONS.END_SUCCESS, payload: stateData });
        return stateData;
      } catch (err) {
        console.warn('Backend endSession error, transitioning to completed locally:', err.message);
        const fallbackData = {
          session_id: state.sessionId,
          status: finalStatus,
          current_step: 'complete',
        };
        dispatch({ type: ACTIONS.END_SUCCESS, payload: fallbackData });
        return fallbackData;
      }
    },
    [state.sessionId, state.ending, state.loading]
  );

  /**
   * Reset the classroom state completely back to initial state.
   */
  const resetClassroom = useCallback(() => {
    dispatch({ type: ACTIONS.RESET });
  }, []);

  /**
   * Clear active error status.
   */
  const clearError = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_ERROR });
  }, []);

  /**
   * Clear active question evaluation feedback.
   */
  const clearEvaluation = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_EVALUATION });
  }, []);

  /**
   * Store active final assessment package.
   */
  const setAssessmentPackage = useCallback((pkg) => {
    dispatch({ type: ACTIONS.SET_ASSESSMENT_PACKAGE, payload: pkg });
  }, []);

  /**
   * Store final assessment diagnostic evaluation report.
   */
  const setAssessmentReport = useCallback((report) => {
    dispatch({ type: ACTIONS.SET_ASSESSMENT_REPORT, payload: report });
  }, []);

  /**
   * Set the interactive state of the AI Teacher (e.g. listening, encouraging, thinking)
   */
  const setTeacherState = useCallback((newState) => {
    dispatch({ type: ACTIONS.SET_TEACHER_STATE, payload: newState });
  }, []);

  const value = {
    // Complete State
    ...state,

    // Actions
    startClassroomSession,
    advanceTeachingStep,
    submitAnswer,
    switchLanguage,
    refreshSession,
    endClassroomSession,
    resetClassroom,
    clearError,
    clearEvaluation,
    setAssessmentPackage,
    setAssessmentReport,
    setTeacherState,
  };

  return (
    <ClassroomContext.Provider value={value}>
      {children}
    </ClassroomContext.Provider>
  );
}

/**
 * Helper to retrieve stored active session for seamless recovery
 */
export function getStoredActiveSession() {
  try {
    const raw = localStorage.getItem('ai_teacher_active_session');
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Custom hook to consume the unified Classroom state engine.
 */
export function useClassroom() {
  const context = useContext(ClassroomContext);
  if (!context) {
    throw new Error('useClassroom must be used within a ClassroomProvider');
  }
  return context;
}

export default ClassroomContext;
