import React from 'react';

export default function ToolTimeline({ traces, onClose }) {
  const getStageClass = (stage) => {
    switch (stage) {
      case 'Query Rewriting':
        return 'warning';
      case 'RAG Retrieval':
        return 'active';
      case 'Tool Selection':
      case 'Tool Execution':
        return 'success';
      case 'Tool Response':
        return 'active';
      case 'Action Cancelled':
        return 'error';
      default:
        return '';
    }
  };

  return (
    <div className="side-panel" style={{ width: '380px' }}>
      <div className="panel-header">
        <span className="panel-title">Execution Timeline</span>
        <button 
          className="btn" 
          onClick={onClose} 
          style={{ padding: '2px 8px', fontSize: '11px', background: 'transparent' }}
        >
          ✕ Close
        </button>
      </div>
      <div className="panel-content">
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          This panel streams backend orchestration details, showing query transformations, RAG document hits, and MCP tool execution in real-time.
        </p>

        {traces.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 0',
            opacity: 0.4,
            textAlign: 'center'
          }}>
            <span style={{ fontSize: '24px', marginBottom: '8px' }}>📡</span>
            <span style={{ fontSize: '12px' }}>Waiting for next query request...</span>
          </div>
        ) : (
          <div className="timeline-list">
            {traces.map((trace, idx) => (
              <div 
                key={idx} 
                className={`timeline-node ${getStageClass(trace.stage)}`}
                style={{ marginBottom: '4px' }}
              >
                <div className="timeline-dot" />
                <div className="timeline-stage">{trace.stage}</div>
                <div className="timeline-details">
                  {trace.details}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
