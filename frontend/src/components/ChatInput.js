import React, { useState } from 'react';
import '../styles/ChatInput.css';

function ChatInput({ onSendMessage, loading }) {
  const [message, setMessage] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !loading) {
      onSendMessage(message);
      setMessage('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="chat-input-container" onSubmit={handleSubmit}>
      <div className="input-wrapper">
        <textarea
          className="message-input"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask me anything... (Shift+Enter for new line)"
          disabled={loading}
          rows="1"
        />
        <button 
          type="submit" 
          className="send-button" 
          disabled={!message.trim() || loading}
          title="Send message"
        >
          {loading ? '⏳' : '➤'}
        </button>
      </div>
    </form>
  );
}

export default ChatInput;
