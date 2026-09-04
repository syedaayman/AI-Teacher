import React from 'react';

const NAV_ITEMS = [
  { id: 'health', label: '1. System Health', badge: 'P1' },
  { id: 'materials', label: '2. Material Processing', badge: 'P2' },
  { id: 'rag', label: '3. RAG Retrieval', badge: 'P3' },
  { id: 'concepts', label: '4. Concepts & Graph', badge: 'P4' },
  { id: 'lessons', label: '5. Lesson Planner', badge: 'P4' },
  { id: 'assessment', label: '6. Assessment', badge: 'P5' },
  { id: 'adaptive', label: '7. Adaptive Engine', badge: 'P6' },
  { id: 'learner', label: '8. Learner Profile', badge: 'P7' },
  { id: 'pipeline', label: '9. Guided Pipeline', badge: 'E2E' },
  { id: 'raw-json', label: '10. Raw API / JSON', badge: 'Logs' },
];

export default function Sidebar({ activeTab, onSelectTab }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">
          <span>🧠</span> AI Brain Dashboard
        </div>
        <div className="sidebar-subtitle">Member 1 Dev / Test Console</div>
      </div>

      <ul className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <li
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => onSelectTab(item.id)}
          >
            <span>{item.label}</span>
            <span className="phase-badge">{item.badge}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
