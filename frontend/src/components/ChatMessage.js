import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../styles/ChatMessage.css';

function ChatMessage({ message, sources }) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`chat-message ${isUser ? 'user-message' : 'assistant-message'}`}>
      <div className="message-content">
        {isUser ? (
          <div className="user-text">{message.content}</div>
        ) : (
          <div className="assistant-text">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node, ...props }) => (
                  <table className="markdown-table" {...props} />
                ),
                thead: ({ node, ...props }) => (
                  <thead className="table-header" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="table-header-cell" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="table-data-cell" {...props} />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
      
      {sources && sources.length > 0 && !isUser && (
        <div className="message-sources">
          <details>
            <summary>📄 Sources ({sources.length})</summary>
            <ul>
              {sources.map((doc) => (
                <li key={doc.id}>
                  <strong>{doc.filename}</strong> (Page {doc.page_number})
                  <p className="source-preview">{doc.preview}</p>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </div>
  );
}

export default ChatMessage;
