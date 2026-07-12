import React from 'react';

export default function IngestionView({ 
  statusInfo, 
  onTriggerIngestion, 
  isIngesting,
  onTriggerEvaluation,
  isEvaluating,
  onRefreshStatus
}) {
  const vstore = statusInfo?.vector_store || {};
  const mcp = statusInfo?.mcp_server || {};
  const llmProvider = statusInfo?.llm_provider || 'Unknown';
  const latestEval = statusInfo?.latest_evaluation || null;

  return (
    <div className="ingest-view" style={{ padding: '16px', background: '#0a0a0a', borderBottom: '1px solid #1a1a1a' }}>
      <div className="ingest-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
        
        {/* Left Side: System Telemetry */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--accent-color)' }}>
              🤖 System Status & Registry
            </h3>
            
            <div className="ingest-stats" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>LLM Core Provider</span>
                <span className="stat-val" style={{ textTransform: 'capitalize', fontWeight: 'bold', fontSize: '12px' }}>
                  {llmProvider}
                </span>
              </div>
              
              <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Vector Database</span>
                <span className="stat-val" style={{ fontWeight: 'bold', fontSize: '12px' }}>
                  {vstore.total_chunks !== undefined ? `${vstore.total_chunks} chunks` : 'Disconnected'}
                </span>
              </div>

              <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>MCP Tools Registry</span>
                <span className="stat-val" style={{ fontWeight: 'bold', fontSize: '12px' }}>
                  {mcp.active ? `${mcp.tool_count || 0} tools active` : 'Inactive'}
                </span>
              </div>

              {mcp.active && mcp.tools && (
                <div className="stat-item" style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingTop: '4px' }}>
                  <span className="stat-label" style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Exposed MCP Tools:</span>
                  <span className="stat-val" style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--accent-color)' }}>
                    {mcp.tools.join(', ')}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
            <button 
              className="btn btn-primary" 
              onClick={onTriggerIngestion}
              disabled={isIngesting}
              style={{ padding: '6px 14px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}
            >
              {isIngesting ? '⚡ Syncing docs...' : '⚡ Sync Document Index'}
            </button>
          </div>
        </div>

        {/* Right Side: RAG Quality Evaluation Metrics */}
        <div style={{ borderLeft: '1px solid #1a1a1a', paddingLeft: '32px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--accent-color)' }}>
                📊 RAG Quality Metrics
              </h3>
              <button 
                onClick={onRefreshStatus}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Refresh Metrics Stats"
              >
                🔄 Refresh
              </button>
            </div>

            {latestEval ? (
              <div className="ingest-stats" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                  <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Retrieval Recall@3</span>
                  <span className="stat-val" style={{ color: (latestEval.mean_recall >= 0.8 ? '#4caf50' : '#f44336'), fontWeight: 'bold', fontSize: '12px' }}>
                    {(latestEval.mean_recall * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                  <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Lexical Groundedness</span>
                  <span className="stat-val" style={{ color: (latestEval.mean_groundedness >= 0.6 ? '#4caf50' : '#f44336'), fontWeight: 'bold', fontSize: '12px' }}>
                    {(latestEval.mean_groundedness * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="stat-item" style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #151515', paddingBottom: '4px' }}>
                  <span className="stat-label" style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Response Latency</span>
                  <span className="stat-val" style={{ color: 'var(--accent-color)', fontWeight: 'bold', fontSize: '12px' }}>
                    {latestEval.mean_latency.toFixed(2)}s
                  </span>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Last Audit Run: {latestEval.timestamp} ({latestEval.total_cases} queries)
                </div>
              </div>
            ) : (
              <div style={{ padding: '12px 0', color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.4' }}>
                No evaluation data available yet. Run the RAG Quality Eval Pipeline to measure retrieval accuracy and factual groundedness.
              </div>
            )}
          </div>

          <div style={{ marginTop: '16px' }}>
            <button 
              className="btn btn-secondary" 
              onClick={onTriggerEvaluation}
              disabled={isEvaluating}
              style={{ padding: '6px 14px', fontSize: '11px', border: '1px solid #222', background: '#111', color: '#ccc', textTransform: 'uppercase', letterSpacing: '0.5px', cursor: 'pointer' }}
            >
              {isEvaluating ? '📊 Running Quality Audit...' : '📊 Run RAG Quality Eval'}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
