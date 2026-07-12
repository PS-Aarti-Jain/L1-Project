import React from 'react';

export default function CitationsSidebar({ citation, onClose, retrievedChunks }) {
  if (!citation) return null;

  const { fileName, headingPath } = citation;

  // Search cached chunks from timeline for a matching source file and heading path
  const matchingChunk = retrievedChunks?.find(chunk => {
    const meta = chunk.metadata;
    return (
      meta.source_file === fileName &&
      (meta.heading_path === headingPath || (!meta.heading_path && !headingPath))
    );
  });

  return (
    <div className="side-panel">
      <div className="panel-header">
        <span className="panel-title">Citation Viewer</span>
        <button 
          className="btn" 
          onClick={onClose} 
          style={{ padding: '2px 8px', fontSize: '11px', background: 'transparent' }}
        >
          ✕ Close
        </button>
      </div>
      <div className="panel-content">
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '13px', color: 'var(--color-accent)', marginBottom: '4px' }}>
            Source Document
          </h4>
          <code style={{ fontSize: '11px', background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px' }}>
            {fileName}
          </code>
        </div>

        {headingPath && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ fontSize: '13px', color: 'var(--color-cyan)', marginBottom: '4px' }}>
              Heading Path
            </h4>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              {headingPath}
            </div>
          </div>
        )}

        <h4 style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
          Grounded Context Snippet
        </h4>

        {matchingChunk ? (
          <div className="citation-view">
            <div className="citation-meta">
              Chunk ID: {matchingChunk.metadata?.chunk_id || 'N/A'}
            </div>
            <div className="citation-text">
              {matchingChunk.document}
            </div>
          </div>
        ) : (
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px dashed var(--border-color)',
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            fontSize: '12px'
          }}>
            Could not find full snippet in current query cache. 
            The answer was grounded in this document section.
          </div>
        )}
      </div>
    </div>
  );
}
