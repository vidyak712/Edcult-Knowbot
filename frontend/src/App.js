import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import './styles/ChatbotLayout.css';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import ConversationList from './components/ConversationList';
import { useAuth } from './context/AuthContext';
import { KnowBotAPIClient } from './services/KnowBotAPIClient';

function App() {
  const { user, isAuthenticated, isLoading, login, logout, getApiToken } = useAuth();
  const apiClient = useRef(null);
  
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [messageOffset, setMessageOffset] = useState(0);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const messagesEndRef = useRef(null);
  
  // Initialize API client when user changes
  useEffect(() => {
    if (user) {
      apiClient.current = new KnowBotAPIClient(user, getApiToken);
      console.log('API Client initialized for user:', user.mail);
    }
  }, [user]);

  // Initialize conversation on component mount
  useEffect(() => {
    let sessionId = sessionStorage.getItem('conversationId');
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('conversationId', sessionId);
    }
    setConversationId(sessionId);
    if (user) {
      loadConversationHistory(sessionId);
    }
  }, [user]); // loadConversationHistory is stable due to useCallback

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Load conversation history with pagination
  const loadConversationHistory = useCallback(async (convId, offset = 0) => {
    try {
      if (!apiClient.current) return;

      const data = await apiClient.current.getConversationHistory(convId, 50, offset);
      if (data.messages) {
        if (offset === 0) {
          setMessages(data.messages);
          setMessageOffset(50);
        } else {
          setMessages((prev) => [...data.messages, ...prev]);
          setMessageOffset(offset + data.messages.length);
        }
        setHasMoreMessages(data.has_more);
      }
    } catch (err) {
      console.error('Error loading conversation history:', err);
    }
  }, []); // Empty deps because we use refs and functional state updates

  const handleLoadMoreMessages = async () => {
    if (!hasMoreMessages || loadingMore) return;
    setLoadingMore(true);
    await loadConversationHistory(conversationId, messageOffset);
    setLoadingMore(false);
  };

  // Handle new message from user
  const handleSendMessage = async (userMessage) => {
    if (!userMessage.trim() || !conversationId) return;

    // Add user message immediately to UI
    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, newUserMessage]);
    setError(null);
    setLoading(true);

    try {
      if (!apiClient.current) {
        setError('API client not initialized. Please refresh the page.');
        setLoading(false);
        return;
      }

      // Call LLM endpoint via API client
      const response = await apiClient.current.getLLMResponse(
        userMessage,
        conversationId,
        4
      );

      // Add assistant message to chat
      const assistantMessage = {
        role: 'assistant',
        content: response.llm_response,
        timestamp: new Date().toISOString(),
        sources: response.documents
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Update conversations list
      updateConversationsList();
    } catch (err) {
      setError('Error generating response: ' + (err.message || 'Unknown error'));
      // Remove the user message if request failed
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  // Update conversations list
  const updateConversationsList = () => {
    // Get first user message as title
    const firstUserMsg = messages.find((msg) => msg.role === 'user');
    const title = firstUserMsg
      ? firstUserMsg.content.substring(0, 30) + '...'
      : 'Conversation';

    setConversations((prev) => {
      const existing = prev.find((c) => c.id === conversationId);
      if (existing) {
        return prev.map((c) =>
          c.id === conversationId
            ? {
                ...c,
                lastMessageTime: new Date().toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit'
                })
              }
            : c
        );
      } else {
        return [
          {
            id: conversationId,
            title: title,
            lastMessageTime: new Date().toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })
          },
          ...prev
        ];
      }
    });
  };

  // Start a new conversation
  const handleNewConversation = () => {
    // Show confirmation if there are messages
    if (messages.length > 0) {
      if (!window.confirm('Start a new chat? Current conversation will be saved.')) {
        return;
      }
      // Save current conversation to list before clearing
      updateConversationsList();
    }

    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem('conversationId', newSessionId);
    setConversationId(newSessionId);
    setMessages([]);
    setMessageOffset(0);
    setHasMoreMessages(false);
    setError(null);
  };

  // Load an existing conversation
  const handleSelectConversation = (convId) => {
    setConversationId(convId);
    sessionStorage.setItem('conversationId', convId);
    setMessageOffset(0);
    setHasMoreMessages(false);
    loadConversationHistory(convId);
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: '16px' }}>
        <h1>KnowBot Assistant</h1>
        <button
          onClick={login}
          style={{ padding: '12px 28px', fontSize: '16px', cursor: 'pointer', borderRadius: '6px', border: 'none', background: '#0078d4', color: 'white' }}
        >
          Sign in with Microsoft
        </button>
      </div>
    );
  }

  return (
    <div className="chatbot-app">
      <ConversationList
        conversations={conversations}
        currentConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      <div className="chat-container">
        <div className="chat-header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <div>
              <h1>KnowBot Assistant</h1>
              <p>Ask me anything about your documents</p>
              {user && <p style={{ fontSize: '13px', color: '#666' }}>Signed in as {user.displayName || user.mail}</p>}
            </div>
            {user && (
              <button
                onClick={logout}
                style={{
                  padding: '8px 16px',
                  background: '#d13438',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  whiteSpace: 'nowrap'
                }}
              >
                Sign Out
              </button>
            )}
          </div>
        </div>

        <div className="messages-area">
          {hasMoreMessages && (
            <div style={{ textAlign: 'center', padding: '16px', marginBottom: '8px' }}>
              <button 
                style={{
                  padding: '8px 16px',
                  background: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: loadingMore ? 'not-allowed' : 'pointer',
                  opacity: loadingMore ? 0.6 : 1,
                  fontSize: '13px'
                }}
                onClick={handleLoadMoreMessages}
                disabled={loadingMore}
              >
                {loadingMore ? '⏳ Loading...' : '📜 Load Earlier Messages'}
              </button>
            </div>
          )}

          {messages.length === 0 && !loading && (
            <div className="welcome-container">
              <div className="welcome-message">
                <h2>Welcome to KnowBot</h2>
                <p>Start a conversation by asking a question about your documents.</p>
                <div className="example-questions">
                  <p style={{ fontSize: '12px', color: '#666', marginTop: '16px' }}>
                    Example questions:
                  </p>
                  <ul style={{ fontSize: '13px', color: '#666', marginLeft: '20px' }}>
                    <li>What are the main topics covered?</li>
                    <li>Tell me about the specifications</li>
                    <li>What is the process for...?</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <ChatMessage
              key={index}
              message={message}
              sources={message.sources}
            />
          ))}

          {loading && (
            <div className="chat-message assistant-message">
              <div className="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}

          {error && (
            <div className="error-message-chat">
              <strong>Error:</strong> {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <ChatInput onSendMessage={handleSendMessage} loading={loading} />
      </div>
    </div>
  );
}

export default App;
