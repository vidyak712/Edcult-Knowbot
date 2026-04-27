// frontend/src/context/MockAuthContext.js
/**
 * Mock Authentication Context for Local Testing
 * Simulates Entra ID user authentication without Azure setup
 * 
 * Usage:
 * <MockAuthProvider>
 *   <App />
 * </MockAuthProvider>
 */

import React, { createContext, useState, useEffect, useCallback } from 'react';

export const MockAuthContext = createContext();

// Session timeout: 1 day (24 hours)
//const SESSION_TIMEOUT = 24 * 60 * 60 * 1000; // 86400000 ms
//const WARNING_TIME = 5 * 60 * 1000; // 5 minutes before timeout
const SESSION_TIMEOUT = 60000
const WARNING_TIME = 60000


// Predefined mock users for testing
export const MOCK_USERS = {
  engineer1: {
    oid: '12345678-1234-1234-1234-123456789001',
    mail: 'engineer1@company.com',
    upn: 'engineer1@company.com',
    displayName: 'Alice Engineer',
    givenName: 'Alice',
    surname: 'Engineer',
    jobTitle: 'Senior Engineer',
    officeLocation: 'San Francisco',
    accountEnabled: true
  },
  engineer2: {
    oid: '12345678-1234-1234-1234-123456789002',
    mail: 'engineer2@company.com',
    upn: 'engineer2@company.com',
    displayName: 'Bob Developer',
    givenName: 'Bob',
    surname: 'Developer',
    jobTitle: 'Software Developer',
    officeLocation: 'New York',
    accountEnabled: true
  },
  manager: {
    oid: '12345678-1234-1234-1234-123456789003',
    mail: 'manager@company.com',
    upn: 'manager@company.com',
    displayName: 'Carol Manager',
    givenName: 'Carol',
    surname: 'Manager',
    jobTitle: 'Engineering Manager',
    officeLocation: 'Boston',
    accountEnabled: true
  },
  analyst: {
    oid: '12345678-1234-1234-1234-123456789004',
    mail: 'analyst@company.com',
    upn: 'analyst@company.com',
    displayName: 'David Analyst',
    givenName: 'David',
    surname: 'Analyst',
    jobTitle: 'Data Analyst',
    officeLocation: 'Remote',
    accountEnabled: true
  }
};

/**
 * Mock Auth Provider Component
 * Provides authentication context without requiring Azure AD
 */
export function MockAuthProvider({ children, defaultUser = 'engineer1' }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionExpireTime, setSessionExpireTime] = useState(null);
  const [showSessionWarning, setShowSessionWarning] = useState(false);

  // Initialize session timeout checker
  useEffect(() => {
    const savedUser = localStorage.getItem('mockAuthUser');
    const savedLoginTime = localStorage.getItem('mockAuthLoginTime');
    
    const initialUser = savedUser 
      ? JSON.parse(savedUser) 
      : MOCK_USERS[defaultUser];
    
    // Check if session has expired
    if (savedLoginTime) {
      const loginTime = parseInt(savedLoginTime);
      const now = Date.now();
      const sessionAge = now - loginTime;
      
      if (sessionAge > SESSION_TIMEOUT) {
        // Session expired
        setIsAuthenticated(false);
        setUser(null);
        localStorage.removeItem('mockAuthUser');
        localStorage.removeItem('mockAuthLoginTime');
        setIsLoading(false);
        return;
      }
      
      // Set new expiry time
      const newExpireTime = loginTime + SESSION_TIMEOUT;
      setSessionExpireTime(newExpireTime);
    } else if (initialUser) {
      // New session - set login time
      const now = Date.now();
      localStorage.setItem('mockAuthLoginTime', now.toString());
      setSessionExpireTime(now + SESSION_TIMEOUT);
    }
    
    setUser(initialUser);
    setIsAuthenticated(true);
    setIsLoading(false);
  }, [defaultUser]);

  // Monitor session expiration
  useEffect(() => {
    if (!isAuthenticated || !sessionExpireTime) return;

    const checkSessionExpiry = setInterval(() => {
      const now = Date.now();
      const timeRemaining = sessionExpireTime - now;

      // Show warning 5 minutes before expiry
      if (timeRemaining > 0 && timeRemaining <= WARNING_TIME && !showSessionWarning) {
        setShowSessionWarning(true);
        console.warn(`⏰ Session expiring in ${Math.floor(timeRemaining / 1000 / 60)} minutes`);
      }

      // Auto-logout when expired
      if (timeRemaining <= 0) {
        handleSessionTimeout();
      }
    }, 1000); // Check every second

    return () => clearInterval(checkSessionExpiry);
  }, [isAuthenticated, sessionExpireTime, showSessionWarning]);

  // Handle session timeout
  const handleSessionTimeout = useCallback(() => {
    console.error('❌ Session expired - logging out');
    setIsAuthenticated(false);
    setUser(null);
    setShowSessionWarning(false);
    setSessionExpireTime(null);
    localStorage.removeItem('mockAuthUser');
    localStorage.removeItem('mockAuthLoginTime');
    alert('Your session has expired. Please refresh the page to log in again.');
  }, []);

  /**
   * Switch to a different mock user
   * @param {string} userId - Key from MOCK_USERS
   */
  const switchUser = (userId) => {
    const selectedUser = MOCK_USERS[userId];
    if (selectedUser) {
      setUser(selectedUser);
      localStorage.setItem('mockAuthUser', JSON.stringify(selectedUser));
      
      // Reset session timer when switching users
      const now = Date.now();
      localStorage.setItem('mockAuthLoginTime', now.toString());
      setSessionExpireTime(now + SESSION_TIMEOUT);
      setShowSessionWarning(false);
      
      return selectedUser;
    }
    return null;
  };

  /**
   * Simulate login
   */
  const login = () => {
    setIsAuthenticated(true);
    const defaultUserObj = Object.values(MOCK_USERS)[0];
    setUser(defaultUserObj);
    localStorage.setItem('mockAuthUser', JSON.stringify(defaultUserObj));
    
    // Set session timer
    const now = Date.now();
    localStorage.setItem('mockAuthLoginTime', now.toString());
    setSessionExpireTime(now + SESSION_TIMEOUT);
    setShowSessionWarning(false);
  };

  /**
   * Simulate logout
   */
  const logout = () => {
    setIsAuthenticated(false);
    setUser(null);
    setShowSessionWarning(false);
    setSessionExpireTime(null);
    localStorage.removeItem('mockAuthUser');
    localStorage.removeItem('mockAuthLoginTime');
  };

  /**
   * Create a new mock user
   */
  const addCustomUser = (userId, userDetails) => {
    MOCK_USERS[userId] = {
      oid: `custom-oid-${Date.now()}`,
      ...userDetails,
      accountEnabled: true
    };
    return MOCK_USERS[userId];
  };

  const value = {
    user,
    isAuthenticated,
    isLoading,
    switchUser,
    login,
    logout,
    addCustomUser,
    allUsers: MOCK_USERS,
    accounts: user ? [user] : [], // For MSAL compatibility
    sessionExpireTime,
    showSessionWarning,
    handleSessionTimeout,
    SESSION_TIMEOUT
  };

  return (
    <MockAuthContext.Provider value={value}>
      {children}
    </MockAuthContext.Provider>
  );
}

/**
 * Hook to use mock authentication
 */
export function useMockAuth() {
  const context = React.useContext(MockAuthContext);
  if (!context) {
    throw new Error('useMockAuth must be used within MockAuthProvider');
  }
  return context;
}
