/**
 * Example Chat Component using KnowBotAPIClient
 * Demonstrates integration with Entra ID and backend API
 */

import React, { useContext, useState, useEffect } from 'react';
import { createAPIClient } from '../services/KnowBotAPIClient';
// import { AuthContext } from './path/to/AuthProvider'; // Your Entra ID context

export function ExampleChatComponent() {
  // const { user } = useContext(AuthContext); // Get from your auth provider
  const user = {
    mail: 'user@company.com', // Example
    displayName: 'User Name'
  };

  const [apiClient, setApiClient] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conversationId] = useState('conv_' + Date.now()); // Generate unique ID

  // Initialize API client with user context
  useEffect(() => {
    if (user) {
      const client = createAPIClient(user);
      setApiClient(client);
      loadConversationHistory(client);
    }
  }, [user]);

  // Load conversation history
  const loadConversationHistory = async (client) => {
    try {
      setLoading(true);
      const history = await client.getConversationHistory(conversationId);
      setMessages(history.messages || []);
    } catch (err) {
      setError(err.message);
      console.error('Failed to load conversation history:', err);
    } finally {
      setLoading(false);
    }
  };

  // Handle sending a message
  const handleSendMessage = async (userQuery) => {
    if (!apiClient) {
      setError('API client not initialized');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Add user message to display immediately
      const userMessage = {
        role: 'user',
        content: userQuery,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, userMessage]);

      // Get LLM response from backend
      const response = await apiClient.getLLMResponse(
        userQuery,
        conversationId,
        4 // top_docs
      );

      // Add assistant message
      const assistantMessage = {
        role: 'assistant',
        content: response.llm_response,
        documents: response.documents,
        tokens: response.token_usage,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, assistantMessage]);

    } catch (err) {
      setError(err.message);
      console.error('Error sending message:', err);
      
      // Remove the user message on error
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  // Render message
  const renderMessage = (message) => {
    return (
      <div key={message.timestamp} className={`message ${message.role}`}>
        <div className="message-header">
          <span className="role">{message.role === 'user' ? 'You' : 'Assistant'}</span>
          <span className="time">{new Date(message.timestamp).toLocaleTimeString()}</span>
        </div>
        <div className="message-content">{message.content}</div>
        
        {message.documents && message.documents.length > 0 && (
          <div className="documents">
            <details>
              <summary>📄 {message.documents.length} Documents Used</summary>
              <ul>
                {message.documents.map((doc, idx) => (
                  <li key={idx}>
                    <strong>{doc.filename || `Document ${idx + 1}`}</strong>
                    {doc.page_number && ` (Page ${doc.page_number})`}
                    <p>{doc.preview}</p>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}

        {message.tokens && (
          <div className="tokens">
            <small>
              Tokens: {message.tokens.total_tokens} 
              (prompt: {message.tokens.prompt_tokens}, 
              completion: {message.tokens.completion_tokens})
            </small>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="chat-container">
      <header>
        <h1>KnowBot Chat</h1>
        {user && <p>Logged in as: {user.displayName}</p>}
      </header>

      {error && (
        <div className="error-banner">
          ⚠️ Error: {error}
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className="conversation">
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <p>Start a conversation by typing your question below.</p>
          </div>
        )}

        {messages.map(renderMessage)}

        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>Processing your message...</p>
          </div>
        )}
      </div>

      <footer>
        <ChatInput onSend={handleSendMessage} disabled={loading || !apiClient} />
      </footer>
    </div>
  );
}

/**
 * Simple chat input component
 */
function ChatInput({ onSend, disabled }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      onSend(input.trim());
      setInput('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask me anything..."
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !input.trim()}>
        Send
      </button>
    </form>
  );
}

export default ExampleChatComponent;
