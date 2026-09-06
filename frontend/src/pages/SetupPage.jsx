import React, { useState } from 'react';
import { useClassroom } from '../context/ClassroomContext';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

/**
 * SetupPage Component
 * Compact, lightweight, student-first learning launch.
 * Follows strict design guidelines:
 * - Lilac + Powder Blue + White palette
 * - Non-bulky, compact segmented pills and slim inputs
 * - Step 1: Topic or Material
 * - Step 2: Personalization (Level, Goal, Time, Style, Language, Depth)
 * - Step 3: Lesson Plan Preview with "Start Lesson →"
 */
export default function SetupPage({ onNavigate }) {
  const { startClassroomSession, starting, loading: classroomLoading } = useClassroom();
  const { session: testSession, updateSession } = useTestSession() || { session: {}, updateSession: () => {} };

  // Wizard Step: 1 (Focus), 2 (Personalization), 3 (Lesson Plan Preview)
  const [currentStep, setCurrentStep] = useState(1);

  const initialTopic = typeof testSession?.selectedConcept === 'string'
    ? testSession.selectedConcept
    : testSession?.selectedConcept?.name || '';

  // Step 1: Focus
  const [mode, setMode] = useState(testSession?.materialId ? 'material' : 'topic'); // 'topic' | 'material'
  const [topic, setTopic] = useState(initialTopic || 'Data Structures and Algorithms');
  const [naturalInstruction, setNaturalInstruction] = useState('');
  const [materialId, setMaterialId] = useState(testSession?.materialId || '');
  const [materialFilename, setMaterialFilename] = useState(testSession?.materialFilename || '');
  const [materialDoc, setMaterialDoc] = useState(testSession?.materialDocument || null);
  const [uploadingMaterial, setUploadingMaterial] = useState(false);

  // Step 2: Personalization (Strict Options)
  const [level, setLevel] = useState('Beginner'); // Beginner, Intermediate, Advanced
  const [learningGoal, setLearningGoal] = useState('Understand'); // Understand, Exam, Interview, Problem solving, Practical learning
  const [timeChoice, setTimeChoice] = useState('20 min'); // 5 min, 20 min, 60 min, 7 days, Custom
  const [customMinutes, setCustomMinutes] = useState(20);
  const [teachingStyle, setTeachingStyle] = useState('Simple'); // Simple, Examples, Visual, Step-by-step, Technical
  const [language, setLanguage] = useState('English'); // English, Hindi, Hinglish
  const [depth, setDepth] = useState('Standard'); // Quick, Standard, Deep

  // Step 3: Lesson Plan
  const [planningLoading, setPlanningLoading] = useState(false);
  const [planningMessage, setPlanningMessage] = useState('Preparing your lesson plan...');
  const [learningPlan, setLearningPlan] = useState(null);

  // Error Message
  const [error, setError] = useState(null);

  const SUGGESTED_TOPICS = [
    'Data Structures and Algorithms',
    'Binary Search Trees',
    "Newton's Laws of Motion",
    'Photosynthesis & Plant Biology',
    'Machine Learning Fundamentals',
  ];

  // Helper: map time choice to integer minutes for backend
  const getSelectedMinutes = () => {
    if (timeChoice === '5 min') return 5;
    if (timeChoice === '20 min') return 20;
    if (timeChoice === '60 min') return 60;
    if (timeChoice === '7 days') return 60;
    return Math.max(1, Math.min(180, parseInt(customMinutes, 10) || 20));
  };

  // Material upload handler
  const handleFileUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    setUploadingMaterial(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', 1000);
    formData.append('chunk_overlap', 200);
    formData.append('auto_ingest', true);

    try {
      const data = await api.processMaterial(formData);
      const extracted = data.extracted_document;
      if (extracted) {
        setMaterialId(extracted.material_id);
        setMaterialFilename(extracted.filename);
        setMaterialDoc(extracted);
        if (extracted.topics && extracted.topics.length > 0 && !topic) {
          setTopic(extracted.topics[0]);
        }
        if (updateSession) {
          updateSession({
            materialDocument: extracted,
            materialId: extracted.material_id,
            materialFilename: extracted.filename,
          });
        }
      }
    } catch (err) {
      setError('We could not read this document right now. Please try again or type a topic.');
    } finally {
      setUploadingMaterial(false);
    }
  };

  const handleNextFromStep1 = (e) => {
    e.preventDefault();
    setError(null);
    if (mode === 'topic' && !topic.trim()) {
      setError('Please tell your teacher what you want to learn.');
      return;
    }
    if (mode === 'material' && !materialId.trim()) {
      setError('Please upload a study document to continue.');
      return;
    }
    setCurrentStep(2);
  };

  // Step 2 Submission: Create My Lesson →
  const handleCreateLessonPlan = async (e) => {
    e.preventDefault();
    setError(null);
    setPlanningLoading(true);
    setPlanningMessage('Preparing a lesson specifically for you...');

    try {
      let syllabusData = null;
      if (mode === 'material' && materialDoc) {
        syllabusData = await api.planLessons({
          document: materialDoc,
          title: topic || materialFilename,
        });
      } else {
        syllabusData = await api.planLessons({
          topic: topic.trim(),
          title: topic.trim(),
        });
      }

      if (syllabusData && syllabusData.lessons && syllabusData.lessons.length > 0) {
        setLearningPlan(syllabusData);
        if (updateSession) {
          updateSession({
            syllabus: syllabusData,
            selectedLesson: syllabusData.lessons[0],
          });
        }
      } else {
        setLearningPlan({
          course_title: topic,
          lessons: [
            {
              lesson_id: 'lesson_1',
              title: topic,
              estimated_minutes: getSelectedMinutes(),
              learning_objectives: [
                `Understand the core concepts of ${topic}`,
                `Work through clear examples and step-by-step intuition`,
                `Test your understanding with check questions`,
              ],
              concepts: [
                `${topic} Fundamentals`,
                `Core Principles & Intuition`,
                `Practical Examples`,
                `Practice & Assessment`,
              ],
            },
          ],
        });
      }
      setCurrentStep(3);
    } catch (err) {
      // Fallback graceful plan
      setLearningPlan({
        course_title: topic || 'Custom Lesson',
        lessons: [
          {
            lesson_id: 'lesson_1',
            title: topic || 'Foundations',
            estimated_minutes: getSelectedMinutes(),
            learning_objectives: [
              `Learn fundamental concepts of ${topic}`,
              `Practice with interactive teacher guidance`,
            ],
            concepts: [
              `Introduction to ${topic}`,
              `Key Techniques & Demonstration`,
              `Interactive Questions`,
              `Summary Assessment`,
            ],
          },
        ],
      });
      setCurrentStep(3);
    } finally {
      setPlanningLoading(false);
    }
  };

  // Step 3 Submission: Start Lesson →
  const handleStartTeaching = async () => {
    setError(null);
    try {
      const backendDepth = depth === 'Quick' ? 'quick_overview' : depth === 'Deep' ? 'deep_dive' : 'standard';
      const backendDifficulty = level.toLowerCase();
      const backendLanguage = language.toLowerCase();
      const finalTopic = mode === 'topic' ? topic.trim() : (topic.trim() || materialFilename);

      await startClassroomSession({
        learner_id: 'student_1',
        topic: finalTopic,
        material_id: mode === 'material' ? materialId.trim() : null,
        available_time_minutes: getSelectedMinutes(),
        desired_depth: backendDepth,
        preferred_language: backendLanguage,
        preferred_difficulty: backendDifficulty,
      });

      if (typeof onNavigate === 'function') {
        onNavigate('classroom');
      }
    } catch (err) {
      setError("We couldn't prepare your lesson right now. Please try again.");
    }
  };

  return (
    <div className="compact-setup-wrapper">
      {/* Stepper Navigation */}
      <div className="compact-stepper-bar">
        <div className={`stepper-step ${currentStep >= 1 ? 'active' : ''}`}>
          <span className="step-circle">1</span>
          <span className="step-title">Choose Topic</span>
        </div>
        <div className="stepper-divider" />
        <div className={`stepper-step ${currentStep >= 2 ? 'active' : ''}`}>
          <span className="step-circle">2</span>
          <span className="step-title">Personalize</span>
        </div>
        <div className="stepper-divider" />
        <div className={`stepper-step ${currentStep === 3 ? 'active' : ''}`}>
          <span className="step-circle">3</span>
          <span className="step-title">Lesson Plan</span>
        </div>
      </div>

      {error && (
        <div className="compact-error-banner" role="alert">
          <span className="error-icon">ℹ️</span>
          <span className="error-text">{error}</span>
          <button type="button" className="btn-error-dismiss" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* STEP 1: Choose Topic or Upload Material */}
      {currentStep === 1 && (
        <div className="compact-card">
          <div className="compact-card-header">
            <h2 className="compact-card-title">What would you like to learn?</h2>
            <p className="compact-card-subtitle">
              Choose a topic to explore or upload notes to learn directly from your material.
            </p>
          </div>

          {/* Mode Switcher */}
          <div className="compact-segmented-control" role="tablist">
            <button
              type="button"
              className={`segmented-pill ${mode === 'topic' ? 'selected' : ''}`}
              onClick={() => setMode('topic')}
            >
              📖 Learn a Topic
            </button>
            <button
              type="button"
              className={`segmented-pill ${mode === 'material' ? 'selected' : ''}`}
              onClick={() => setMode('material')}
            >
              📄 Learn From My Material
            </button>
          </div>

          <form onSubmit={handleNextFromStep1} className="compact-form">
            {mode === 'topic' ? (
              <div className="form-field-group">
                <label htmlFor="topic-input" className="field-label">What do you want to learn?</label>
                <input
                  id="topic-input"
                  type="text"
                  className="field-input"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Data Structures, Physics, Machine Learning..."
                  autoFocus
                  required
                />

                <div className="field-subgroup">
                  <label htmlFor="instruction-input" className="field-sublabel">
                    Natural instructions (optional):
                  </label>
                  <input
                    id="instruction-input"
                    type="text"
                    className="field-input subinput"
                    value={naturalInstruction}
                    onChange={(e) => setNaturalInstruction(e.target.value)}
                    placeholder="e.g. I'm a beginner. Teach me DSA in 20 minutes using simple examples."
                  />
                </div>

                <div className="compact-suggestions-row">
                  <span className="suggestions-label">Popular topics:</span>
                  <div className="suggestions-pills">
                    {SUGGESTED_TOPICS.map((t, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="pill-tag"
                        onClick={() => setTopic(t)}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="form-field-group">
                <label className="field-label">Upload your material (PDF, DOC, DOCX, PPT, PPTX)</label>
                <div className="compact-upload-container">
                  <input
                    type="file"
                    id="material-upload-input"
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.txt"
                    onChange={handleFileUpload}
                    className="file-input-hidden"
                    disabled={uploadingMaterial}
                  />
                  <label htmlFor="material-upload-input" className="compact-dropzone">
                    <span className="upload-emoji">📎</span>
                    {uploadingMaterial ? (
                      <span className="dropzone-text">
                        <LoadingSpinner size="sm" text="Reading your document..." inline color="text-indigo-500" />
                      </span>
                    ) : materialFilename ? (
                      <span className="dropzone-text">
                        <strong>{materialFilename}</strong>
                        <small className="dropzone-sub">Click to change file</small>
                      </span>
                    ) : (
                      <span className="dropzone-text">
                        <strong>Click to select your document</strong>
                        <small className="dropzone-sub">PDF, DOC, DOCX, PPT, PPTX</small>
                      </span>
                    )}
                  </label>
                </div>

                {materialFilename && (
                  <div className="field-subgroup mt-2">
                    <label htmlFor="material-topic-focus" className="field-sublabel">
                      What would you like to learn from this?
                    </label>
                    <input
                      id="material-topic-focus"
                      type="text"
                      className="field-input subinput"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g. Chapter 1, Key Algorithms, or entire document"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="compact-actions-row">
              <button type="submit" className="btn-compact btn-compact-primary">
                Continue to Personalization →
              </button>
            </div>
          </form>
        </div>
      )}

      {/* STEP 2: Personalization */}
      {currentStep === 2 && (
        <div className="compact-card">
          <div className="compact-card-header">
            <h2 className="compact-card-title">Personalize Your Lesson</h2>
            <p className="compact-card-subtitle">
              Tell your teacher your preferences so the lesson adapts specifically to you.
            </p>
          </div>

          {planningLoading ? (
            <div className="compact-loading-state">
              <LoadingSpinner size="medium" text={planningMessage} color="text-indigo-500" />
              <span className="loading-sub">Preparing personalized concepts, visuals, and check questions...</span>
            </div>
          ) : (
            <form onSubmit={handleCreateLessonPlan} className="compact-form">
              {/* 1. Your Level */}
              <div className="preference-group">
                <span className="preference-label">Your level:</span>
                <div className="pills-selection-row">
                  {['Beginner', 'Intermediate', 'Advanced'].map((lvl) => (
                    <button
                      key={lvl}
                      type="button"
                      className={`compact-choice-pill ${level === lvl ? 'active' : ''}`}
                      onClick={() => setLevel(lvl)}
                    >
                      {lvl}
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. Learning Goal */}
              <div className="preference-group">
                <span className="preference-label">Learning goal:</span>
                <div className="pills-selection-row">
                  {['Understand', 'Exam preparation', 'Interview preparation', 'Problem solving', 'Practical learning'].map((goal) => (
                    <button
                      key={goal}
                      type="button"
                      className={`compact-choice-pill ${learningGoal === goal ? 'active' : ''}`}
                      onClick={() => setLearningGoal(goal)}
                    >
                      {goal}
                    </button>
                  ))}
                </div>
              </div>

              {/* 3. Available Time */}
              <div className="preference-group">
                <span className="preference-label">Available time:</span>
                <div className="pills-selection-row">
                  {['5 min', '20 min', '60 min', '7 days', 'Custom'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={`compact-choice-pill ${timeChoice === t ? 'active' : ''}`}
                      onClick={() => setTimeChoice(t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                {timeChoice === 'Custom' && (
                  <div className="custom-minutes-inline">
                    <label htmlFor="custom-min-input" className="custom-min-label">Minutes:</label>
                    <input
                      id="custom-min-input"
                      type="number"
                      min="1"
                      max="180"
                      className="field-input slim-number"
                      value={customMinutes}
                      onChange={(e) => setCustomMinutes(Math.max(1, Math.min(180, parseInt(e.target.value, 10) || 1)))}
                    />
                  </div>
                )}
              </div>

              {/* 4. Teaching Preference */}
              <div className="preference-group">
                <span className="preference-label">Teaching preference:</span>
                <div className="pills-selection-row">
                  {['Simple', 'Examples', 'Visual', 'Step-by-step', 'Technical'].map((style) => (
                    <button
                      key={style}
                      type="button"
                      className={`compact-choice-pill ${teachingStyle === style ? 'active' : ''}`}
                      onClick={() => setTeachingStyle(style)}
                    >
                      {style}
                    </button>
                  ))}
                </div>
              </div>

              {/* 5. Language */}
              <div className="preference-group">
                <span className="preference-label">Language:</span>
                <div className="pills-selection-row">
                  {['English', 'Hindi', 'Hinglish'].map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      className={`compact-choice-pill ${language === lang ? 'active' : ''}`}
                      onClick={() => setLanguage(lang)}
                    >
                      {lang}
                    </button>
                  ))}
                </div>
              </div>

              {/* 6. Depth */}
              <div className="preference-group">
                <span className="preference-label">Desired depth:</span>
                <div className="pills-selection-row">
                  {['Quick', 'Standard', 'Deep'].map((d) => (
                    <button
                      key={d}
                      type="button"
                      className={`compact-choice-pill ${depth === d ? 'active' : ''}`}
                      onClick={() => setDepth(d)}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="compact-actions-row space-between">
                <button
                  type="button"
                  className="btn-compact btn-compact-secondary"
                  onClick={() => setCurrentStep(1)}
                >
                  ← Back
                </button>
                <button type="submit" className="btn-compact btn-compact-primary">
                  Create My Lesson →
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* STEP 3: Learning Plan Preview */}
      {currentStep === 3 && (
        <div className="compact-card">
          <div className="compact-card-header">
            <h2 className="compact-card-title">Your Lesson Plan</h2>
            <p className="compact-card-subtitle">
              {learningPlan?.course_title || (mode === 'topic' ? topic : materialFilename)}
            </p>
          </div>

          <div className="plan-summary-chips">
            <span className="plan-chip">⏱️ {getSelectedMinutes()} min</span>
            <span className="plan-chip">🎯 {learningGoal}</span>
            <span className="plan-chip">🗣️ {language}</span>
            <span className="plan-chip">📊 {level}</span>
          </div>

          {/* Objectives if available */}
          {learningPlan?.lessons && learningPlan.lessons[0]?.learning_objectives && (
            <div className="plan-objectives-box">
              <span className="objectives-title">Learning Objective:</span>
              <ul className="objectives-list">
                {learningPlan.lessons[0].learning_objectives.map((obj, i) => (
                  <li key={i}>{obj}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Concepts List in Elegant Compact Sequence */}
          <div className="plan-timeline-container">
            <span className="timeline-title">Lesson Sequence:</span>
            <ol className="compact-concept-timeline">
              {(() => {
                const lesson = learningPlan?.lessons?.[0];
                const rawConcepts = lesson?.concepts || [
                  'Arrays',
                  'Traversal',
                  'Searching',
                  'Sorting',
                  'Practice',
                  'Assessment',
                ];

                return rawConcepts.map((item, idx) => {
                  const conceptTitle = typeof item === 'string' ? item : item?.name || `Concept ${idx + 1}`;
                  const numStr = String(idx + 1).padStart(2, '0');

                  return (
                    <li key={idx} className="timeline-step-row">
                      <span className="step-badge-num">{numStr}</span>
                      <span className="step-name-text">{conceptTitle}</span>
                      {idx === 0 && <span className="step-first-indicator">Starting Here</span>}
                    </li>
                  );
                });
              })()}
            </ol>
          </div>

          <div className="compact-actions-row space-between">
            <button
              type="button"
              className="btn-compact btn-compact-secondary"
              onClick={() => setCurrentStep(2)}
              disabled={starting || classroomLoading}
            >
              ← Edit Preferences
            </button>
            <button
              type="button"
              className="btn-compact btn-compact-primary"
              onClick={handleStartTeaching}
              disabled={starting || classroomLoading}
            >
              {starting ? (
                <LoadingSpinner size="sm" text="Preparing your teacher..." inline color="text-white" />
              ) : (
                'Start Lesson →'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
