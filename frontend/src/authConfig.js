// Microsoft Entra ID (Azure AD) MSAL configuration

export const msalConfig = {
  auth: {
    clientId: '0bc16f0f-965a-432a-905d-273d38a8abd8',
    authority: 'https://login.microsoftonline.com/6a892cee-4f29-4e28-878b-7ce916becb73',
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
};

// Scopes for logging in (user profile info)
export const loginRequest = {
  scopes: ['openid', 'profile', 'email'],
};

// Scopes for calling the KnowBot backend API
export const apiRequest = {
  scopes: ['api://24c7980c-0f68-4a7d-8e98-ded139cab71c/access_as_user'],
};