// frontend/src/context/AuthContext.js
// Real Entra ID authentication using MSAL

import { useMemo, useCallback } from 'react';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { InteractionRequiredAuthError, InteractionStatus } from '@azure/msal-browser';
import { apiRequest, loginRequest } from '../authConfig';

/**
 * Hook to use Entra ID authentication via MSAL.
 * Drop-in replacement for useMockAuth().
 */
export function useAuth() {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const isLoading = inProgress !== InteractionStatus.None;

  const account = accounts[0] || null;

  // Normalise user shape to match what components expect
  // Use useMemo to prevent creating new object on every render
  const user = useMemo(() => 
    account
      ? {
          oid: account.localAccountId,
          mail: account.username,
          upn: account.username,
          displayName: account.name,
          name: account.name,
        }
      : null,
    [account?.localAccountId, account?.username, account?.name]
  );

  const login = () => instance.loginRedirect(loginRequest);

  const logout = () => instance.logoutRedirect({ account });

  /**
   * Acquire a Bearer token for the KnowBot API silently.
   * Falls back to redirect if interaction is required.
   */
  const getApiToken = useCallback(async () => {
    if (!account) throw new Error('Not authenticated');
    try {
      const response = await instance.acquireTokenSilent({
        ...apiRequest,
        account,
      });
      return response.accessToken;
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        await instance.acquireTokenRedirect({ ...apiRequest, account });
      }
      throw error;
    }
  }, [account, instance]);

  return { user, isAuthenticated, isLoading, login, logout, getApiToken, accounts };
}
