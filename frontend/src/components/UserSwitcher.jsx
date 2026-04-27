// frontend/src/components/UserSwitcher.jsx
/**
 * User Switcher Component for Local Testing
 * Allows quickly switching between mock Entra ID users
 * Shows session timeout status
 */

import React, { useState, useEffect } from 'react';
import { useMockAuth } from '../context/MockAuthContext';
import '../styles/UserSwitcher.css'; // See CSS file below

export function UserSwitcher() {
  const { user, switchUser, allUsers, sessionExpireTime, showSessionWarning, handleSessionTimeout, SESSION_TIMEOUT } = useMockAuth();
  const [timeRemaining, setTimeRemaining] = useState(null);

  // Update time remaining
  useEffect(() => {
    if (!sessionExpireTime) return;

    const updateTimer = setInterval(() => {
      const now = Date.now();
      const remaining = sessionExpireTime - now;
      
      if (remaining <= 0) {
        setTimeRemaining('Expired');
      } else {
        const hours = Math.floor(remaining / (1000 * 60 * 60));
        const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((remaining % (1000 * 60)) / 1000);
        setTimeRemaining(`${hours}h ${minutes}m ${seconds}s`);
      }
    }, 1000);

    return () => clearInterval(updateTimer);
  }, [sessionExpireTime]);

  const getSessionStatusColor = () => {
    if (!sessionExpireTime) return '#888';
    const remaining = sessionExpireTime - Date.now();
    if (remaining <= 5 * 60 * 1000) return '#d32f2f'; // Red: < 5 min
    if (remaining <= 30 * 60 * 1000) return '#f57c00'; // Orange: < 30 min
    return '#388e3c'; // Green
  };

  return (
    <div className="user-switcher">
      {/* Session Warning Banner */}
      {showSessionWarning && (
        <div className="session-warning">
          ⏰ <strong>Session Expiring Soon!</strong> Your session will end in {timeRemaining}. 
          <button onClick={() => window.location.reload()}>Refresh to Continue</button>
        </div>
      )}

      <details>
        <summary>
          👤 <strong>Current User:</strong> {user?.displayName || 'Not Authenticated'}
        </summary>

        <div className="user-switcher-content">
          <p className="current-user-info">
            <strong>User ID:</strong> {user?.mail || 'N/A'}<br />
            <strong>Object ID:</strong> {user?.oid || 'N/A'}<br />
            <strong>Job Title:</strong> {user?.jobTitle || 'N/A'}<br />
            <strong>Office:</strong> {user?.officeLocation || 'N/A'}
          </p>

          {/* Session Status */}
          <div className="session-status" style={{ borderLeftColor: getSessionStatusColor() }}>
            <strong>Session Status</strong><br />
            <strong>Expires in:</strong> <span style={{ color: getSessionStatusColor() }}>{timeRemaining || 'Loading...'}</span><br />
            <small>Total session duration: 24 hours from login</small>
          </div>

          <div className="user-list">
            <p className="section-title">Switch Test User:</p>
            <div className="user-buttons">
              {Object.entries(allUsers).map(([key, userData]) => (
                <button
                  key={key}
                  className={`user-button ${user?.mail === userData.mail ? 'active' : ''}`}
                  onClick={() => switchUser(key)}
                  title={`${userData.displayName} (${userData.mail})`}
                >
                  <div className="user-button-name">{userData.displayName}</div>
                  <div className="user-button-email">{userData.mail}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="user-info">
            <p className="debug-info">
              <small>
                ℹ️ This switcher is for local development only.<br />
                Each user has isolated conversation history.<br />
                Session timeout: 24 hours from login
              </small>
            </p>
          </div>
        </div>
      </details>
    </div>
  );
}

export default UserSwitcher;
