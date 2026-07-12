import React, { useState, useEffect } from 'react';

export default function ConfirmationModal({ pendingConfirm, onConfirm, onCancel }) {
  if (!pendingConfirm) return null;

  const { confirmation_id, tool_name, arguments: initialArgs } = pendingConfirm;
  
  // Set up local state for editable fields
  const [fields, setFields] = useState({});

  useEffect(() => {
    if (initialArgs) {
      setFields({ ...initialArgs });
    }
  }, [initialArgs]);

  const handleChange = (key, value) => {
    setFields(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleConfirmSubmit = (e) => {
    e.preventDefault();
    onConfirm(confirmation_id, fields);
  };

  const renderEditableFields = () => {
    if (tool_name === 'github_create_issue') {
      return (
        <>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Repository (owner/repo)</label>
            <input 
              type="text" 
              value={fields.repo || ''} 
              onChange={(e) => handleChange('repo', e.target.value)} 
              placeholder="e.g. octocat/Hello-World"
            />
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Issue Title</label>
            <input 
              type="text" 
              value={fields.title || ''} 
              onChange={(e) => handleChange('title', e.target.value)} 
              placeholder="Issue title"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Issue Description (Body)</label>
            <textarea 
              value={fields.body || ''} 
              onChange={(e) => handleChange('body', e.target.value)} 
              placeholder="Issue description (markdown supported)"
              rows={6}
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                padding: '10px 14px',
                borderRadius: '6px',
                outline: 'none',
                fontFamily: 'inherit',
                fontSize: '13px',
                resize: 'vertical'
              }}
              required
            />
          </div>
        </>
      );
    }

    if (tool_name === 'github_comment_pr') {
      return (
        <>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Repository (owner/repo)</label>
            <input 
              type="text" 
              value={fields.repo || ''} 
              onChange={(e) => handleChange('repo', e.target.value)} 
              placeholder="e.g. octocat/Hello-World"
            />
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>PR / Issue Number</label>
            <input 
              type="number" 
              value={fields.pr_number || ''} 
              onChange={(e) => handleChange('pr_number', parseInt(e.target.value, 10))} 
              placeholder="e.g. 42"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Comment Content</label>
            <textarea 
              value={fields.comment || ''} 
              onChange={(e) => handleChange('comment', e.target.value)} 
              placeholder="Comment text (markdown supported)"
              rows={5}
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                padding: '10px 14px',
                borderRadius: '6px',
                outline: 'none',
                fontFamily: 'inherit',
                fontSize: '13px',
                resize: 'vertical'
              }}
              required
            />
          </div>
        </>
      );
    }

    // Fallback for general tools if schema differs
    return (
      <div className="proposal-value-body">
        <pre>{JSON.stringify(fields, null, 2)}</pre>
      </div>
    );
  };

  return (
    <div className="modal-overlay">
      <form className="modal-content" onSubmit={handleConfirmSubmit}>
        <div className="modal-header">
          <div className="modal-icon">⚠️</div>
          <span className="modal-title">GitHub Action Approval Needed</span>
        </div>
        <div className="modal-body">
          <p className="modal-desc">
            DevAssist wants to perform a write operation on GitHub using the tool: 
            <strong style={{ color: 'var(--color-cyan)', fontFamily: 'monospace' }}> {tool_name}</strong>.
            Review and adjust the parameters below before confirming.
          </p>

          <div className="tool-proposal-card">
            <div className="proposal-label">Edit Parameters</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {renderEditableFields()}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button 
            type="button" 
            className="btn btn-danger" 
            onClick={() => onCancel(confirmation_id)}
          >
            ✕ Reject & Abort
          </button>
          <button 
            type="submit" 
            className="btn btn-primary"
          >
            ✓ Approve & Execute
          </button>
        </div>
      </form>
    </div>
  );
}
