import React from 'react';
import '../styles/ConversationList.css';

function ConversationList({ conversations, currentConversationId, onSelectConversation, onNewConversation }) {
  return (
    <div className="conversation-sidebar">
      <div className="sidebar-header">
        <h2>Conversations</h2>
        <button 
          className="new-chat-button"
          onClick={onNewConversation}
          title="Start a new conversation"
        >
          ➕ New Chat
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <p className="no-conversations">No conversations yet</p>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${conv.id === currentConversationId ? 'active' : ''}`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'Untitled'}
              </div>
              <div className="conversation-time">
                {conv.lastMessageTime}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default ConversationList;
