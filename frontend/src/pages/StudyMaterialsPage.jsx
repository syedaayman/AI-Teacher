import React, { useState } from 'react';
import { useTestSession } from '../context/TestSessionContext';
import api from '../services/api';

/**
 * StudyMaterialsPage Component
 * Clean, student-friendly library of study documents, textbooks, and lecture notes.
 * Allows uploading PDF, DOC/DOCX, PPT/PPTX and launching lessons directly.
 */
export default function StudyMaterialsPage({ onNavigate }) {
  const { session: testSession, updateSession } = useTestSession() || { session: {}, updateSession: () => {} };
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Initial curated / uploaded materials list
  const [materials, setMaterials] = useState(() => {
    const list = [
      {
        id: 'mat_dsa_notes',
        name: 'Data Structures & Algorithms Notes.pdf',
        type: 'PDF',
        icon: '📄',
        size: '2.4 MB',
        date: 'Recent',
        topics: ['Arrays', 'Binary Trees', 'Hash Tables'],
      },
      {
        id: 'mat_physics_ch4',
        name: 'Physics Chapter 4 - Mechanics & Motion.pdf',
        type: 'PDF',
        icon: '📘',
        size: '4.1 MB',
        date: 'Recent',
        topics: ['Newtonian Laws', 'Momentum', 'Kinetic Energy'],
      },
      {
        id: 'mat_ml_lecture',
        name: 'Introduction to Machine Learning.pptx',
        type: 'PPTX',
        icon: '📊',
        size: '6.8 MB',
        date: 'Recent',
        topics: ['Neural Networks', 'Gradient Descent', 'Loss Functions'],
      },
    ];

    if (testSession?.materialFilename && testSession?.materialId) {
      if (!list.some((m) => m.id === testSession.materialId)) {
        list.unshift({
          id: testSession.materialId,
          name: testSession.materialFilename,
          type: testSession.materialFilename.split('.').pop().toUpperCase(),
          icon: '📄',
          size: 'Uploaded',
          date: 'Just now',
          topics: ['Key Concepts', 'Chapter Summary'],
        });
      }
    }
    return list;
  });

  const handleFileUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', 1000);
    formData.append('chunk_overlap', 200);
    formData.append('auto_ingest', true);

    try {
      const data = await api.processMaterial(formData);
      const doc = data.extracted_document;
      if (doc) {
        const newEntry = {
          id: doc.material_id,
          name: doc.filename,
          type: doc.filename.split('.').pop().toUpperCase(),
          icon: '📄',
          size: `${Math.max(1, Math.round(doc.character_count / 1024))} KB`,
          date: 'Just now',
          topics: ['Key Concepts', 'Chapter 1'],
        };
        setMaterials((prev) => [newEntry, ...prev.filter((m) => m.id !== doc.material_id)]);
        if (updateSession) {
          updateSession({
            materialDocument: doc,
            materialId: doc.material_id,
            materialFilename: doc.filename,
          });
        }
        setSuccessMessage(`"${doc.filename}" is ready to learn from!`);
      }
    } catch (err) {
      setError(err.message || 'Unable to prepare document. Please try another file.');
    } finally {
      setUploading(false);
    }
  };

  const handleLearnFrom = (item) => {
    if (updateSession) {
      updateSession({
        materialId: item.id,
        materialFilename: item.name,
      });
    }
    if (typeof onNavigate === 'function') {
      onNavigate('learn');
    }
  };

  return (
    <div className="study-materials-container">
      {/* Header */}
      <header className="materials-header">
        <div>
          <h1 className="materials-title">My Study Materials</h1>
          <p className="materials-subtitle">
            Upload notes, lecture slides, and textbooks for your AI Teacher to teach from.
          </p>
        </div>

        <div className="upload-cta-box">
          <input
            type="file"
            id="lib-file-upload"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.txt"
            onChange={handleFileUpload}
            className="file-input-hidden"
            disabled={uploading}
          />
          <label htmlFor="lib-file-upload" className="btn btn-primary btn-pill">
            {uploading ? 'Reading Document...' : '+ Upload Study Material'}
          </label>
        </div>
      </header>

      {/* Notifications */}
      {successMessage && (
        <div className="materials-alert alert-success" role="alert">
          <span>✓</span> {successMessage}
        </div>
      )}
      {error && (
        <div className="materials-alert alert-error" role="alert">
          <span>⚠️</span> {error}
        </div>
      )}

      {/* Upload Zone */}
      <div className="materials-dropzone-card">
        <label htmlFor="lib-file-upload" className="lib-dropzone-inner">
          <span className="dropzone-emoji">📂</span>
          <div className="dropzone-text">
            <strong>Drop new notes or textbook chapters here</strong>
            <small>Supports PDF, Word (DOC/DOCX), and PowerPoint (PPT/PPTX)</small>
          </div>
          <span className="btn btn-secondary btn-sm">Browse Files</span>
        </label>
      </div>

      {/* Documents Grid */}
      <section className="materials-grid-section" aria-label="Available Study Documents">
        <h2 className="section-title mb-3">Your Ready Documents</h2>
        <div className="materials-cards-grid">
          {materials.map((item) => (
            <div key={item.id} className="material-card card-hover">
              <div className="material-card-top">
                <span className="material-file-icon">{item.icon}</span>
                <span className="material-badge">{item.type}</span>
              </div>

              <div className="material-card-body">
                <h3 className="material-file-name" title={item.name}>
                  {item.name}
                </h3>
                <div className="material-file-meta">
                  <span>{item.size}</span>
                  <span>•</span>
                  <span>{item.date}</span>
                </div>

                {item.topics && item.topics.length > 0 && (
                  <div className="material-topics-pills">
                    {item.topics.map((t, idx) => (
                      <span key={idx} className="material-topic-pill">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="material-card-footer">
                <button
                  type="button"
                  className="btn btn-primary btn-sm btn-full"
                  onClick={() => handleLearnFrom(item)}
                >
                  Learn From This →
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
