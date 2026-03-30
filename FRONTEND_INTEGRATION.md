# Frontend Integration with Entra ID and Backend API

## Backend API Updates

### 1. **LLM Response Endpoint**
**POST** `/api/llm-response`

Now requires `user_id` in the request body:

```json
{
  "query": "What are the site and environmental conditions?",
  "conversationId": "conv_001",
  "user_id": "user@company.com",
  "top_docs": 4
}
```

### 2. **Conversation History Endpoint**
**GET** `/api/conversation-history/{conversation_id}?user_id=USER_ID&limit=50&offset=0`

Now requires `user_id` as a query parameter:
- `user_id` (required): User ID from Entra ID authentication
- `conversation_id` (path): Conversation ID
- `limit` (optional): Number of messages (default: 50)
- `offset` (optional): Pagination offset (default: 0)

---

## Frontend Integration Examples

### React Component with Entra ID

```javascript
import { useContext } from 'react';
import { AuthContext } from './AuthProvider'; // Your Entra ID context

export function ChatComponent() {
  const { user } = useContext(AuthContext); // user.mail or user.upn for email
  
  const getUserId = () => {
    // Extract user ID from Entra ID - use email or unique ID
    return user?.mail || user?.upn || user?.oid;
  };

  // Call LLM API
  const generateResponse = async (query, conversationId) => {
    try {
      const response = await fetch('/api/llm-response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          conversationId: conversationId,
          user_id: getUserId(), // ✅ Send Entra ID user
          top_docs: 4
        })
      });
      
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error:', error);
    }
  };

  // Get conversation history
  const getConversationHistory = async (conversationId) => {
    try {
      const userId = getUserId();
      const response = await fetch(
        `/api/conversation-history/${conversationId}?user_id=${userId}&limit=50`,
        { method: 'GET' }
      );
      
      const data = await response.json();
      return data.messages;
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    // Your component JSX
  );
}
```

### Using Axios

```javascript
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

export const apiClient = {
  // Get LLM response
  getLLMResponse: (query, conversationId, userId) => {
    return axios.post(`${API_BASE_URL}/api/llm-response`, {
      query,
      conversationId,
      user_id: userId,
      top_docs: 4
    });
  },

  // Get conversation history
  getConversationHistory: (conversationId, userId, limit = 50, offset = 0) => {
    return axios.get(
      `${API_BASE_URL}/api/conversation-history/${conversationId}`,
      {
        params: {
          user_id: userId,
          limit,
          offset
        }
      }
    );
  }
};
```

### Usage in ChatComponent

```javascript
import { useContext, useState } from 'react';
import { AuthContext } from './AuthProvider';
import { apiClient } from './api';

export function ChatMessage() {
  const { user } = useContext(AuthContext);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const conversationId = 'conv_001'; // Get from state/URL

  const handleSendMessage = async (userQuery) => {
    setLoading(true);
    try {
      // Call backend with user ID
      const response = await apiClient.getLLMResponse(
        userQuery,
        conversationId,
        user?.mail // From Entra ID
      );

      // Add to conversation
      setMessages([...messages, {
        role: 'user',
        content: userQuery
      }, {
        role: 'assistant',
        content: response.data.llm_response
      }]);
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load conversation history on mount
  useEffect(() => {
    const loadHistory = async () => {
      const history = await apiClient.getConversationHistory(
        conversationId,
        user?.mail
      );
      setMessages(history);
    };
    
    if (user?.mail) {
      loadHistory();
    }
  }, [user?.mail, conversationId]);

  return (
    // Render messages and input
  );
}
```

---

## Entra ID User Properties

When using Entra ID in react-aad-msal or @azure/msal-react:

```javascript
// Available user properties:
user.mail           // Email address
user.upn            // User Principal Name
user.oid             // Object ID (unique identifier)
user.displayName    // Display name
user.givenName      // First name
user.surname        // Last name

// Recommended to use: user.mail or user.oid
```

---

## Environment Variables (Frontend)

```env
REACT_APP_API_URL=http://localhost:3001
# or for production
REACT_APP_API_URL=https://api.yourdomain.com
```

---

## Testing the APIs

### Using cURL

```bash
# LLM Response
curl -X POST http://localhost:3001/api/llm-response \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are site conditions?",
    "conversationId": "conv_001",
    "user_id": "user@company.com",
    "top_docs": 4
  }'

# Conversation History
curl "http://localhost:3001/api/conversation-history/conv_001?user_id=user@company.com&limit=50"
```

### Using Postman

1. **LLM Response**
   - Method: POST
   - URL: `http://localhost:3001/api/llm-response`
   - Body (JSON):
   ```json
   {
     "query": "Your query here",
     "conversationId": "conv_001",
     "user_id": "user@company.com",
     "top_docs": 4
   }
   ```

2. **Conversation History**
   - Method: GET
   - URL: `http://localhost:3001/api/conversation-history/conv_001?user_id=user@company.com&limit=50&offset=0`

---

## Security Notes

✅ **What's now enforced:**
- Backend methods use `user_id` as Cosmos DB partition key
- All queries are single-partition (no cross-partition access)
- Each user only queries their own data

⚠️ **Still needed:**
- Backend authorization: Verify user_id matches authenticated user
- Add token validation middleware
- Implement role-based access control (if needed)

### Add Authorization Middleware (recommended)

```python
from fastapi import Depends, HTTPException, Header
from jose import jwt

async def verify_user_token(authorization: str = Header(None), user_id: str = None):
    """Verify JWT token and user_id match"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        # Decode token and verify user_id
        payload = jwt.decode(token, "your-secret", algorithms=["HS256"])
        if payload.get("sub") != user_id:
            raise HTTPException(status_code=403, detail="User ID mismatch")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    return user_id

# Use in endpoints
@app.post("/api/llm-response")
async def get_llm_response(
    llm_request: LLMRequest,
    verified_user: str = Depends(verify_user_token)
):
    # verified_user == llm_request.user_id
    ...
```
