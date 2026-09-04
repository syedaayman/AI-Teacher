import React, { useState } from 'react';
import { TestSessionProvider } from './context/TestSessionContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
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
  const [activeTab, setActiveTab] = useState('health');

  const renderContent = () => {
    switch (activeTab) {
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
        return <HealthPage />;
    }
  };

  return (
    <TestSessionProvider>
      <div className="app-container">
        <Sidebar activeTab={activeTab} onSelectTab={setActiveTab} />
        <div className="main-wrapper">
          <Header />
          <main className="content-area">{renderContent()}</main>
        </div>
      </div>
    </TestSessionProvider>
  );
}
