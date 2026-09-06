import React, { useState } from 'react';
import { TestSessionProvider } from './context/TestSessionContext';
import { ClassroomProvider } from './context/ClassroomContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import LandingAuthPage from './pages/LandingAuthPage';
import HomePage from './pages/HomePage';
import ClassroomPage from './pages/ClassroomPage';
import SetupPage from './pages/SetupPage';
import MyLearningPage from './pages/MyLearningPage';
import StudyMaterialsPage from './pages/StudyMaterialsPage';
import FinalAssessmentPage from './pages/FinalAssessmentPage';
import AssessmentResultsPage from './pages/AssessmentResultsPage';
import RevisionDashboardPage from './pages/RevisionDashboardPage';
import HealthPage from './pages/HealthPage';
import MaterialsPage from './pages/MaterialsPage';
import RAGPage from './pages/RAGPage';
import ConceptsPage from './pages/ConceptsPage';
import LessonsPage from './pages/LessonsPage';
import AssessmentPage from './pages/AssessmentPage';
import AdaptivePage from './pages/AdaptivePage';
import LearnerProfilePage from './pages/LearnerProfilePage';
import PipelineTestPage from './pages/PipelineTestPage';
import RawJsonPage from './pages/RawJsonPage';

export default function App() {
  // Authentication / User state
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('teachie_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Default to standalone 'landing' if not logged in, otherwise 'home' (Welcome Dashboard)
  const [activeTab, setActiveTab] = useState(() => {
    const saved = localStorage.getItem('teachie_user');
    return saved ? 'home' : 'landing';
  });

  // Auth Action Handlers
  const handleSignIn = (userData) => {
    localStorage.setItem('teachie_user', JSON.stringify(userData));
    setUser(userData);
    setActiveTab('home');
  };

  const handleRegister = (userData) => {
    localStorage.setItem('teachie_user', JSON.stringify(userData));
    setUser(userData);
    setActiveTab('home');
  };

  const handleGuestEnter = (guestData) => {
    const guest = guestData || {
      name: 'Guest Learner',
      email: 'guest@teachie.ai',
      grade: 'Undergraduate / College',
      isGuest: true,
    };
    localStorage.setItem('teachie_user', JSON.stringify(guest));
    setUser(guest);
    setActiveTab('home');
  };

  const handleDirectStartTopic = () => {
    const guest = {
      name: 'Guest Learner',
      email: 'guest@teachie.ai',
      grade: 'Undergraduate / College',
      isGuest: true,
    };
    localStorage.setItem('teachie_user', JSON.stringify(guest));
    setUser(guest);
    setActiveTab('learn');
  };

  const handleSignOut = () => {
    localStorage.removeItem('teachie_user');
    setUser(null);
    setActiveTab('landing');
  };

  // Dashboard content renderer
  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <HomePage onNavigate={setActiveTab} user={user} />;
      case 'my-learning':
        return <MyLearningPage onNavigate={setActiveTab} user={user} />;
      case 'learn':
      case 'setup':
        return <SetupPage onNavigate={setActiveTab} />;
      case 'classroom':
        return <ClassroomPage onNavigate={setActiveTab} />;
      case 'study-materials':
        return <StudyMaterialsPage onNavigate={setActiveTab} />;
      case 'assessments':
      case 'final-assessment':
        return <FinalAssessmentPage onNavigate={setActiveTab} />;
      case 'assessment-results':
        return <AssessmentResultsPage onNavigate={setActiveTab} />;
      case 'revision':
        return <RevisionDashboardPage onNavigate={setActiveTab} />;
      case 'health':
        return <HealthPage />;
      case 'materials':
        return <MaterialsPage />;
      case 'rag':
        return <RAGPage />;
      case 'concepts':
        return <ConceptsPage />;
      case 'lessons':
        return <LessonsPage />;
      case 'assessment':
        return <AssessmentPage />;
      case 'adaptive':
        return <AdaptivePage />;
      case 'learner':
        return <LearnerProfilePage />;
      case 'pipeline':
        return <PipelineTestPage />;
      case 'raw-json':
        return <RawJsonPage />;
      default:
        return <ClassroomPage onNavigate={setActiveTab} />;
    }
  };

  // 1. STANDALONE LANDING & AUTH PAGE (OUTSIDE DASHBOARD)
  if (activeTab === 'landing') {
    return (
      <ClassroomProvider>
        <TestSessionProvider>
          <LandingAuthPage
            onSignIn={handleSignIn}
            onRegister={handleRegister}
            onGuestEnter={handleGuestEnter}
            onDirectStartTopic={handleDirectStartTopic}
            onNavigate={(tab) => {
              if (tab === 'landing') {
                setActiveTab('landing');
              } else {
                if (!user) {
                  handleGuestEnter();
                }
                setActiveTab(tab);
              }
            }}
          />
        </TestSessionProvider>
      </ClassroomProvider>
    );
  }

  // 2. AUTHENTICATED DASHBOARD (INSIDE SIDEBAR + TOP HEADER)
  return (
    <ClassroomProvider>
      <TestSessionProvider>
        <div className="app-container">
          <Sidebar activeTab={activeTab} onSelectTab={setActiveTab} onSignOut={handleSignOut} />
          <div className="main-wrapper">
            <Header onNavigate={setActiveTab} onSignOut={handleSignOut} user={user} />
            <main className="content-area">
              {renderContent()}
            </main>
          </div>
        </div>
      </TestSessionProvider>
    </ClassroomProvider>
  );
}
