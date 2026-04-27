/**
 * API Client for KnowBot - Handles all backend API calls
 * Automatically includes user_id from Entra ID authentication
 */

//const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://knowbot-backend.orangepebble-f73d9664.uksouth.azurecontainerapps.io';

export class KnowBotAPIClient {
  /**
   * @param {Object} user - Entra ID user object from auth context
   * @param {Function} getToken - Async function that returns a Bearer token for the API
   */
  constructor(user, getToken) {
    this.user = user;
    this.getToken = getToken;
  }

  /**
   * Get LLM response with document context
   * @param {string} query - User query
   * @param {string} conversationId - Conversation identifier
   * @param {number} topDocs - Number of documents to retrieve (default: 4)
   * @returns {Promise<Object>} LLM response with documents and token usage
   */
  async getLLMResponse(query, conversationId, topDocs = 4) {
    const token = await this.getToken();

    try {
      const response = await fetch(`${API_BASE_URL}/api/llm-response`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          query,
          conversationId
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get LLM response');
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting LLM response:', error);
      throw error;
    }
  }

  /**
   * Get conversation history with pagination
   * @param {string} conversationId - Conversation identifier
   * @param {number} limit - Number of messages to retrieve (default: 50)
   * @param {number} offset - Pagination offset (default: 0)
   * @returns {Promise<Object>} Conversation messages and metadata
   */
  async getConversationHistory(conversationId, limit = 50, offset = 0) {
    const token = await this.getToken();

    try {
      const params = new URLSearchParams({ limit, offset });

      const response = await fetch(
        `${API_BASE_URL}/api/conversation-history/${conversationId}?${params}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get conversation history');
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting conversation history:', error);
      throw error;
    }
  }

  /**
   * Search documents in Azure Search
   * @param {string} query - Search query
   * @param {string} conversationId - Conversation identifier
   * @param {number} top - Number of results (default: 4)
   * @returns {Promise<Object>} Search results
   */
  async search(query, conversationId, top = 4) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query,
          conversationId,
          top
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Search failed');
      }

      return await response.json();
    } catch (error) {
      console.error('Error searching:', error);
      throw error;
    }
  }

  /**
   * Check health of backend services
   * @returns {Promise<Object>} Health status
   */
  async checkHealth() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Health check failed');
      }

      return await response.json();
    } catch (error) {
      console.error('Error checking health:', error);
      throw error;
    }
  }

  /**
   * Update user context (for token refresh or user change)
   * @param {Object} user - New user object
   */
  updateUser(user) {
    this.user = user;
    this.userId = user?.mail || user?.upn || user?.oid;
  }
}

// Export singleton instance creator
export function createAPIClient(user) {
  return new KnowBotAPIClient(user);
}
