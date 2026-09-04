import React, { createContext, useContext, useState } from 'react';

const TestSessionContext = createContext(null);

const initialSession = {
  materialDocument: null,
  materialId: '',
  materialFilename: '',
  ragResults: [],
  groundedContext: null,
  concepts: [],
  conceptGraph: null,
  topologicalOrder: [],
  syllabus: null,
  selectedLesson: null,
  selectedConcept: null,
  generatedQuestions: [],
  selectedQuestion: null,
  studentAnswer: null,
  evaluationResult: null,
  misconceptionAnalysis: null,
  conceptMastery: null,
  adaptationDecision: null,
  learnerId: 'dev_learner_01',
  learnerProfile: null,
};

export function TestSessionProvider({ children }) {
  const [session, setSession] = useState(initialSession);

  const updateSession = (fields) => {
    setSession((prev) => ({ ...prev, ...fields }));
  };

  const clearTestSession = () => {
    setSession({
      ...initialSession,
      learnerId: `dev_learner_${Math.floor(Math.random() * 900 + 100)}`,
    });
  };

  return (
    <TestSessionContext.Provider value={{ session, updateSession, clearTestSession }}>
      {children}
    </TestSessionContext.Provider>
  );
}

export function useTestSession() {
  const context = useContext(TestSessionContext);
  if (!context) {
    throw new Error('useTestSession must be used within a TestSessionProvider');
  }
  return context;
}
