import React, { useRef, useEffect } from 'react';

export default function ChatPanel({ messages, onCitationClick, isLoading }) {
  const containerRef = useRef(null);

  // Auto-scroll to bottom of chat on new messages
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Helper to parse simple markdown formatting & citation tags
  const renderFormattedText = (text) => {
    if (!text) return '';

    // Regex for matching citation pattern: [filename.md#Section Path] or [filename.md]
    const citationRegex = /\[([a-zA-Z0-9_\-\.]+\.md)(?:#([^\]]+))?\]/g;

    // First, split by code blocks ```code```
    const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
    const parts = [];
    let lastIdx = 0;
    let match;

    // Temporary storage for text parsing
    const parseTextWithCitations = (plainText, keyPrefix) => {
      const subParts = [];
      let subLastIdx = 0;
      let subMatch;

      while ((subMatch = citationRegex.exec(plainText)) !== null) {
        if (subMatch.index > subLastIdx) {
          subParts.push(plainText.substring(subLastIdx, subMatch.index));
        }

        const fileName = subMatch[1];
        const headingPath = subMatch[2] || '';
        const label = headingPath ? `${fileName}#${headingPath}` : fileName;

        subParts.push(
          <button
            key={`cite-${keyPrefix}-${subMatch.index}`}
            className="citation-link"
            onClick={() => onCitationClick(fileName, headingPath)}
            title={`View citation: ${label}`}
          >
            📄 {label}
          </button>
        );

        subLastIdx = citationRegex.lastIndex;
      }

      if (subLastIdx < plainText.length) {
        subParts.push(plainText.substring(subLastIdx));
      }

      return subParts.length > 0 ? subParts : plainText;
    };

    while ((match = codeBlockRegex.exec(text)) !== null) {
      // Process text before code block
      if (match.index > lastIdx) {
        const textBefore = text.substring(lastIdx, match.index);
        parts.push(
          <span key={`text-${lastIdx}`}>
            {textBefore.split('\n').map((line, lIdx) => (
              <span key={lIdx}>
                {parseTextWithCitations(line, `${lastIdx}-${lIdx}`)}
                {lIdx < textBefore.split('\n').length - 1 && <br />}
              </span>
            ))}
          </span>
        );
      }

      const lang = match[1] || 'code';
      const codeVal = match[2];

      parts.push(
        <div key={`code-${match.index}`} className="code-block-container" style={{ margin: '8px 0' }}>
          <div style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            fontFamily: 'monospace',
            marginBottom: '4px',
            textTransform: 'uppercase'
          }}>
            {lang}
          </div>
          <pre>
            <code>{codeVal}</code>
          </pre>
        </div>
      );

      lastIdx = codeBlockRegex.lastIndex;
    }

    // Process remaining text after last code block
    if (lastIdx < text.length) {
      const remainingText = text.substring(lastIdx);
      parts.push(
        <span key={`text-${lastIdx}`}>
          {remainingText.split('\n').map((line, lIdx) => (
            <span key={lIdx}>
              {parseTextWithCitations(line, `${lastIdx}-${lIdx}`)}
              {lIdx < remainingText.split('\n').length - 1 && <br />}
            </span>
          ))}
        </span>
      );
    }

    return parts;
  };

  return (
    <div className="messages-container" ref={containerRef}>
      {messages.length === 0 ? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          opacity: 0.5,
          textAlign: 'center',
          gap: '12px',
          padding: '40px'
        }}>
          <div style={{ fontSize: '40px' }}>🤖</div>
          <h3>Welcome to DevAssist</h3>
          <p style={{ fontSize: '13px', maxWidth: '360px' }}>
            Ask questions about local engineering documentation or request GitHub actions (e.g. creating issues or searching code).
          </p>
        </div>
      ) : (
        messages.map((msg, index) => {
          if (msg.role === 'tool') return null; // Hide raw tool outputs from conversation bubbles
          
          const isUser = msg.role === 'user';
          
          // If assistant message is just tool call and has no text, don't render an empty bubble
          if (!isUser && !msg.content && msg.tool_calls) {
            return null;
          }

          return (
            <div key={index} className={`message-wrapper ${msg.role}`}>
              <div className="message-header">
                {isUser ? '👤 Developer' : '🤖 DevAssist'}
              </div>
              <div className="message-bubble">
                {renderFormattedText(msg.content)}
              </div>
            </div>
          );
        })
      )}

      {isLoading && (
        <div className="message-wrapper assistant">
          <div className="message-header">🤖 DevAssist</div>
          <div className="message-bubble" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Thinking</span>
            <div className="status-dot active" style={{ width: '6px', height: '6px', margin: 0 }} />
          </div>
        </div>
      )}
    </div>
  );
}
