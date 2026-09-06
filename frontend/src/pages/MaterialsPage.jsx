import React, { useState } from 'react';
import { api } from '../services/api';
import { useTestSession } from '../context/TestSessionContext';
import LoadingSpinner from '../components/LoadingSpinner';

export default function MaterialsPage() {
  const { session, updateSession } = useTestSession();
  const [file, setFile] = useState(null);
  const [chunkSize, setChunkSize] = useState(1000);
  const [chunkOverlap, setChunkOverlap] = useState(200);
  const [autoIngest, setAutoIngest] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(session.materialDocument ? { extracted_document: session.materialDocument } : null);
  const [expandedChunkId, setExpandedChunkId] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleProcess = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to process.');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', chunkSize);
    formData.append('chunk_overlap', chunkOverlap);
    formData.append('auto_ingest', autoIngest);

    try {
      const data = await api.processMaterial(formData);
      setResult(data);
      updateSession({
        materialDocument: data.extracted_document,
        materialId: data.extracted_document.material_id,
        materialFilename: data.extracted_document.filename,
      });
    } catch (err) {
      setError(err.message || 'Material processing failed');
    } finally {
      setLoading(false);
    }
  };

  const doc = result?.extracted_document;
  const ingestion = result?.ingestion_result;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📄 Material Processing (Phase 2)</h1>
        <p className="page-description">
          Upload and normalize real learning materials (PDF, DOCX, PPTX, TXT) with hierarchical chunking and deterministic IDs.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>❌</span>
          <div>
            <strong>Processing Error:</strong> {error}
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <div className="card-title">
            <span>Upload Document</span>
          </div>

          <form onSubmit={handleProcess}>
            <div className="form-group">
              <label className="form-label">Choose Learning File (.pdf, .docx, .pptx, .txt)</label>
              <input
                type="file"
                className="form-input"
                accept=".pdf,.docx,.pptx,.txt"
                onChange={handleFileChange}
                disabled={loading}
              />
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Chunk Size (chars)</label>
                <input
                  type="number"
                  className="form-input"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(Number(e.target.value))}
                  min="200"
                  max="4000"
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Chunk Overlap (chars)</label>
                <input
                  type="number"
                  className="form-input"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(Number(e.target.value))}
                  min="0"
                  max="1000"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                id="auto_ingest"
                checked={autoIngest}
                onChange={(e) => setAutoIngest(e.target.checked)}
                disabled={loading}
              />
              <label htmlFor="auto_ingest" style={{ fontSize: '13px', cursor: 'pointer' }}>
                Auto-ingest chunks into ChromaDB Vector Store (Phase 3)
              </label>
            </div>

            <button type="submit" className="btn btn-primary" disabled={loading || !file} style={{ width: '100%' }}>
              {loading ? (
                <LoadingSpinner inline={true} size="small" text="Processing Material..." color="text-white" />
              ) : (
                '⚙️ Process Material'
              )}
            </button>
          </form>
        </div>

        {doc && (
          <div className="card">
            <div className="card-title">
              <span>Extraction & Ingestion Summary</span>
              <span className="badge badge-pass">Processed</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Filename:</span> <strong>{doc.filename}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Material ID:</span>{' '}
                <code style={{ color: '#38bdf8' }}>{doc.material_id}</code>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>File Type:</span>{' '}
                <span className="phase-badge">{doc.file_type?.toUpperCase()}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)' }}>Total Chunks:</span>{' '}
                <strong>{doc.chunks?.length || 0}</strong>
              </div>
              {doc.metadata?.total_pages && (
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Total Pages:</span> {doc.metadata.total_pages}
                </div>
              )}
              {doc.metadata?.total_slides && (
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Total Slides:</span> {doc.metadata.total_slides}
                </div>
              )}

              {ingestion && (
                <div style={{ marginTop: '12px', padding: '10px', background: 'var(--bg-card-alt)', borderRadius: '6px' }}>
                  <div style={{ fontWeight: 600, color: '#34d399', marginBottom: '4px' }}>
                    ✅ ChromaDB Vector Ingestion (Phase 3)
                  </div>
                  <div style={{ fontSize: '12px' }}>
                    Indexed Chunks: <strong>{ingestion.indexed_chunks}</strong> / Total: {ingestion.total_chunks}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Status: {ingestion.status}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {doc && doc.chunks && doc.chunks.length > 0 && (
        <div className="card">
          <div className="card-title">
            <span>Extracted Document Chunks ({doc.chunks.length})</span>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Chunk ID</th>
                  <th>Chapter / Section</th>
                  <th>Page / Slide</th>
                  <th>Text Preview</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {doc.chunks.map((chk, idx) => (
                  <React.Fragment key={chk.chunk_id}>
                    <tr>
                      <td>{idx + 1}</td>
                      <td>
                        <code style={{ fontSize: '11px', color: '#38bdf8' }}>{chk.chunk_id}</code>
                      </td>
                      <td>
                        {chk.chapter || chk.section ? (
                          <span>
                            {chk.chapter} {chk.section ? `> ${chk.section}` : ''}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>-</span>
                        )}
                      </td>
                      <td>
                        {chk.page_number
                          ? `p. ${chk.page_number}`
                          : chk.slide_number
                          ? `slide ${chk.slide_number}`
                          : '-'}
                      </td>
                      <td>{chk.text.length > 100 ? `${chk.text.substring(0, 100)}...` : chk.text}</td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setExpandedChunkId(expandedChunkId === chk.chunk_id ? null : chk.chunk_id)}
                        >
                          {expandedChunkId === chk.chunk_id ? 'Collapse' : 'Expand'}
                        </button>
                      </td>
                    </tr>
                    {expandedChunkId === chk.chunk_id && (
                      <tr>
                        <td colSpan={6} style={{ background: '#090d16', padding: '16px' }}>
                          <div style={{ marginBottom: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                            <strong>Full Chunk Content</strong> | Characters: {chk.text.length} | Metadata:{' '}
                            {JSON.stringify(chk.source_metadata || {})}
                          </div>
                          <div className="code-block" style={{ maxHeight: '200px' }}>
                            {chk.text}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
