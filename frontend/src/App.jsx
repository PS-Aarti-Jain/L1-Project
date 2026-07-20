import React, { useState, useEffect } from 'react';
import ChatPanel from './components/ChatPanel';
import CitationsSidebar from './components/CitationsSidebar';
import ToolTimeline from './components/ToolTimeline';
import ConfirmationModal from './components/ConfirmationModal';
import IngestionView from './components/IngestionView';

const BACKEND_URL = 'http://localhost:8000';

export default function App() {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState('');
  const [loginUser, setLoginUser] = useState('admin');
  const [loginPass, setLoginPass] = useState('password123');
  const [authError, setAuthError] = useState('');

  // Conversation state
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // System stats & administration
  const [statusInfo, setStatusInfo] = useState(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);

  // Tracing, Caching & Citations
  const [traces, setTraces] = useState([]);
  const [retrievedChunks, setRetrievedChunks] = useState([]);
  const [activeCitation, setActiveCitation] = useState(null);
  const [showTimeline, setShowTimeline] = useState(true);

  // Action confirmation state
  const [pendingConfirm, setPendingConfirm] = useState(null);

  // Check for saved token at startup
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      setToken(savedToken);
      setIsAuthenticated(true);
    }
  }, []);

  // Fetch status info when authenticated
  useEffect(() => {
    if (isAuthenticated && token) {
      fetchStatus();
    }
  }, [isAuthenticated, token]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      setStatusInfo(data);
    } catch (err) {
      console.error('Error fetching backend status:', err);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const formData = new URLSearchParams();
      formData.append('username', loginUser);
      formData.append('password', loginPass);

      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: formData.toString()
      });

      if (!res.ok) {
        throw new Error('Invalid credentials. Use admin / password123');
      }

      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setIsAuthenticated(true);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setIsAuthenticated(false);
    setMessages([]);
    setTraces([]);
    setRetrievedChunks([]);
    setActiveCitation(null);
    setPendingConfirm(null);
  };

  const handleTriggerIngestion = async () => {
    setIsIngesting(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/ingest`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await res.json();
      alert(`Sync Complete!\nIndexed ${data.files_indexed} new/changed files.\nSkipped ${data.files_skipped} unchanged files.\nPurged ${data.files_deleted_from_db} deleted files.`);
      fetchStatus();
    } catch (err) {
      alert('Manual ingestion failed: ' + err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleTriggerEvaluation = async () => {
    setIsEvaluating(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/evaluation/run`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to start evaluation pipeline');
      }
      alert('RAG Evaluation pipeline started in the background!\nIt runs 5 test cases and logs the metrics. Please wait 15-20 seconds and click "⚡ Sync Documentation Index" or trigger a chat to fetch status updates.');
      fetchStatus();
    } catch (err) {
      alert('Error starting evaluation: ' + err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  // Consume a JSON line stream returned by the orchestrator API
  const consumeStream = async (response, initialHistory) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    
    // Setup initial assistant response template
    let assistantContent = '';
    const newMessages = [...initialHistory, { role: 'assistant', content: '' }];
    setMessages(newMessages);

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Save the last partial line back to buffer
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          
          try {
            const event = JSON.parse(line);
            
            if (event.type === 'token') {
              assistantContent += event.token;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: assistantContent
                };
                return updated;
              });
            } 
            else if (event.type === 'trace') {
              setTraces(prev => [...prev, { stage: event.stage, details: event.details }]);
            } 
            else if (event.type === 'retrieved_chunks') {
              setRetrievedChunks(prev => [...prev, ...event.chunks]);
            } 
            else if (event.type === 'requires_confirmation') {
              // LLM requested a write operation. Halt loop and display confirmation prompt
              setPendingConfirm({
                confirmation_id: event.confirmation_id,
                tool_name: event.tool_name,
                arguments: event.arguments
              });
              
              // Remove the empty assistant message bubble since it has no content yet
              setMessages(prev => prev.slice(0, -1));
              setIsLoading(false);
              return; // Break consumption
            } 
            else if (event.type === 'error') {
              console.error('LLM internal error:', event.error);
              alert('Error from DevAssist: ' + event.error);
            }
          } catch (e) {
            console.error('Failed to parse stream line:', line, e);
          }
        }
      }
    } catch (err) {
      console.error('Error reading stream chunks:', err);
    } finally {
      setIsLoading(false);
      fetchStatus();
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;

    const query = inputText;
    setInputText('');
    setIsLoading(true);
    setTraces([]); // Reset traces for new turn
    setActiveCitation(null); // Clear sidebar

    // Setup history with user query
    const userMsg = { role: 'user', content: query };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: query,
          history: messages
        })
      });

      if (!res.ok) {
        throw new Error('Network error starting chat stream');
      }

      await consumeStream(res, nextHistory);
    } catch (err) {
      console.error(err);
      alert('Error sending message: ' + err.message);
      setIsLoading(false);
    }
  };

  const handleConfirmAction = async (confId, editedArgs) => {
    setPendingConfirm(null);
    setIsLoading(true);
    setTraces(prev => [...prev, { stage: 'Approval Received', details: 'User approved action execution.' }]);

    try {
      const res = await fetch(`${BACKEND_URL}/api/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          confirmation_id: confId,
          approved: true,
          edited_arguments: editedArgs
        })
      });

      if (!res.ok) {
        throw new Error('Action confirmation API failed');
      }

      // Resume streaming from the orchestrator
      await consumeStream(res, messages);
    } catch (err) {
      alert('Error confirming action: ' + err.message);
      setIsLoading(false);
    }
  };

  const handleCancelAction = async (confId) => {
    setPendingConfirm(null);
    setIsLoading(true);
    setTraces(prev => [...prev, { stage: 'Approval Rejected', details: 'User aborted action execution.' }]);

    try {
      const res = await fetch(`${BACKEND_URL}/api/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          confirmation_id: confId,
          approved: false
        })
      });

      if (!res.ok) {
        throw new Error('Action cancellation API failed');
      }

      // Stream the cancellation explanation response
      await consumeStream(res, messages);
    } catch (err) {
      alert('Error cancelling action: ' + err.message);
      setIsLoading(false);
    }
  };

  const handleCitationClick = (fileName, headingPath) => {
    setActiveCitation({ fileName, headingPath });
  };

  if (!isAuthenticated) {
    return (
      <div className="login-overlay">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="login-header">
            <h2>DevAssist Console</h2>
            <p>RAG + MCP Engineering Knowledge Assistant</p>
          </div>
          {authError && (
            <div style={{ color: 'var(--color-danger)', fontSize: '13px', background: 'rgba(239, 68, 68, 0.1)', padding: '8px', borderRadius: '4px', textAlign: 'center' }}>
              {authError}
            </div>
          )}
          <div className="login-form">
            <div className="form-group">
              <label>Username</label>
              <input 
                type="text" 
                value={loginUser} 
                onChange={(e) => setLoginUser(e.target.value)} 
                required
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input 
                type="password" 
                value={loginPass} 
                onChange={(e) => setLoginPass(e.target.value)} 
                required
              />
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', padding: '12px' }}>
              Sign In to Environment
            </button>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', marginTop: '4px' }}>
              Demo access: use admin / password123
            </div>
            <div style={{ 
              fontSize: '11px', 
              color: 'var(--color-warning)', 
              background: 'rgba(245, 158, 11, 0.1)', 
              border: '1px solid rgba(245, 158, 11, 0.2)',
              padding: '10px', 
              borderRadius: '4px', 
              textAlign: 'center', 
              marginTop: '15px',
              lineHeight: '1.4'
            }}>
              ⚠️ <strong>SECURITY DISCLAIMER:</strong> This console is configured with local demonstration authentication (unsalted SHA-256 hashing, default credentials, browser local storage). It is strictly prohibited to expose this interface to public networks or run it in production.
            </div>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-badge">DEVASSIST</div>
          <span className="app-title">RAG + MCP Documentation Workspace</span>
        </div>
        <div className="header-actions">
          <button 
            className={`btn ${showAdmin ? 'btn-secondary' : ''}`} 
            onClick={() => setShowAdmin(!showAdmin)}
          >
            ⚙️ Control Panel
          </button>
          <button 
            className={`btn ${showTimeline ? 'btn-secondary' : ''}`} 
            onClick={() => setShowTimeline(!showTimeline)}
          >
            📡 Timeline Logs
          </button>
          <button className="btn btn-danger" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {/* Admin Panel */}
      {showAdmin && (
        <IngestionView 
          statusInfo={statusInfo}
          onTriggerIngestion={handleTriggerIngestion}
          isIngesting={isIngesting}
          onTriggerEvaluation={handleTriggerEvaluation}
          isEvaluating={isEvaluating || statusInfo?.is_evaluating}
          onRefreshStatus={fetchStatus}
        />
      )}

      {/* Workspace Area */}
      <div className="app-workspace">
        <div className="chat-workspace">
          {/* Messages */}
          <ChatPanel 
            messages={messages} 
            onCitationClick={handleCitationClick}
            isLoading={isLoading}
          />

          {/* Prompt Entry */}
          <div className="chat-input-container">
            <form className="input-form" onSubmit={handleSendMessage}>
              <input 
                type="text" 
                className="chat-input"
                placeholder="Ask documentation questions or request GitHub tool executions..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={isLoading}
              />
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={isLoading || !inputText.trim()}
              >
                Send Prompt
              </button>
            </form>
          </div>
        </div>

        {/* Tracing Timeline panel */}
        {showTimeline && (
          <ToolTimeline 
            traces={traces} 
            onClose={() => setShowTimeline(false)}
          />
        )}

        {/* Citations panel */}
        {activeCitation && (
          <CitationsSidebar 
            citation={activeCitation}
            onClose={() => setActiveCitation(null)}
            retrievedChunks={retrievedChunks}
          />
        )}
      </div>

      {/* Confirm Action Overlays */}
      {pendingConfirm && (
        <ConfirmationModal 
          pendingConfirm={pendingConfirm}
          onConfirm={handleConfirmAction}
          onCancel={handleCancelAction}
        />
      )}
    </div>
  );
}
