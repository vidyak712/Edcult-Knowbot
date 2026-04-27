import os
import sys
from pathlib import Path

# Add parent directory to path to handle imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import requests
import httpx
from jose import jwt, JWTError
from dotenv import load_dotenv

# Import helpers
from helpers.cosmosDBHelper import CosmosDBHelper
from helpers.app_insights_logger import get_logger

try:
    from azure_llm_handler import generate_response_from_query_with_history
except ImportError:
    from src.azure_llm_handler import generate_response_from_query_with_history

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger("FastAPISearchAPI")

# Initialize FastAPI app
app = FastAPI(
    title="KnowBot Search API",
    description="Azure AI Search API for KnowBot",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Log configuration on startup"""
    logger.info(
        "FastAPI application starting",
        properties={
            "search_endpoint_configured": bool(os.getenv("AZURE_SEARCH_ENDPOINT")),
            "tenant_id_configured": bool(os.getenv("AZURE_TENANT_ID")),
            "api_client_id_configured": bool(os.getenv("AZURE_API_CLIENT_ID")),
            "cosmos_configured": bool(os.getenv("COSMOS_ENDPOINT"))
        }
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Search configuration
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = "index-knowbot-new"
API_VERSION = "2023-11-01"

# Entra ID token validation config
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_API_CLIENT_ID = os.getenv("AZURE_API_CLIENT_ID")

# Log configuration for debugging
if not AZURE_TENANT_ID or not AZURE_API_CLIENT_ID:
    logger.warning(
        "Azure AD configuration missing",
        properties={
            "tenant_id_present": bool(AZURE_TENANT_ID),
            "client_id_present": bool(AZURE_API_CLIENT_ID)
        }
    )

JWKS_URI = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys"
# Accept both v1.0 and v2.0 tokens
TOKEN_ISSUER_V1 = f"https://sts.windows.net/{AZURE_TENANT_ID}/"
TOKEN_ISSUER_V2 = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0"
TOKEN_AUDIENCE = f"api://{AZURE_API_CLIENT_ID}"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SEARCH_ADMIN_KEY
}

# JWT validation
security = HTTPBearer()
_jwks_cache: dict = {}


async def get_jwks() -> dict:
    global _jwks_cache
    if not _jwks_cache:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URI, timeout=10)
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        jwks = await get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            logger.error(
                "Token signing key not found",
                properties={"kid": kid}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signing key not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Try to decode with v2.0 issuer first, fall back to v1.0
        claims = None
        last_error = None
        for issuer in [TOKEN_ISSUER_V2, TOKEN_ISSUER_V1]:
            try:
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256"],
                    audience=TOKEN_AUDIENCE,
                    issuer=issuer,
                )
                logger.info(
                    "Token validated successfully",
                    properties={
                        "issuer": issuer,
                        "user_oid": claims.get("oid"),
                        "email": claims.get("email")
                    }
                )
                break
            except JWTError as e:
                last_error = e
                logger.warning(
                    "Token validation failed for issuer",
                    properties={
                        "issuer": issuer,
                        "error": str(e)
                    }
                )
                continue
        
        if not claims:
            logger.error(
                "Token validation failed for all issuers",
                properties={
                    "expected_audience": TOKEN_AUDIENCE,
                    "error": str(last_error)
                }
            )
            raise JWTError("Token validation failed for both v1.0 and v2.0 issuers")
        
        return claims
    except JWTError as e:
        logger.error(
            "JWT validation error",
            exception=e,
            properties={"error_detail": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(
            "Unexpected error in token validation",
            exception=e,
            properties={"error_type": type(e).__name__}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Pydantic models
class DocumentReference(BaseModel):
    id: str
    filename: Optional[str] = None
    page_number: Optional[int] = None
    preview: str

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMRequest(BaseModel):
    query: str
    conversationId: str
    user_id: Optional[str] = None  # Populated from verified token, not request body

class LLMResponse(BaseModel):
    query: str
    llm_response: str
    documents_used: int
    documents: List[DocumentReference]
    token_usage: TokenUsage

class HealthResponse(BaseModel):
    status: str
    index: str
    endpoint: str

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint - verifies Azure Search connection.
    """
    try:
        # Test connection to Azure Search
        index_url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}"
        response = requests.get(index_url, headers=HEADERS)
        response.raise_for_status()
        
        return HealthResponse(
            status="healthy",
            index=INDEX_NAME,
            endpoint=SEARCH_ENDPOINT
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Azure Search unavailable: {str(e)}"
        )

@app.get("/api/debug/auth-config")
async def debug_auth_config():
    """
    Debug endpoint - shows auth configuration (without secrets).
    """
    return {
        "tenant_id_configured": bool(AZURE_TENANT_ID),
        "api_client_id_configured": bool(AZURE_API_CLIENT_ID),
        "tenant_id_value": AZURE_TENANT_ID if AZURE_TENANT_ID else "NOT_SET",
        "api_client_id_value": AZURE_API_CLIENT_ID if AZURE_API_CLIENT_ID else "NOT_SET",
        "expected_issuers": [TOKEN_ISSUER_V1, TOKEN_ISSUER_V2],
        "expected_audience": TOKEN_AUDIENCE,
        "jwks_uri": JWKS_URI
    }

@app.get("/api/conversation-history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    token_claims: dict = Depends(verify_token),
):
    """
    Retrieve paginated conversation history for a given conversation ID.
    
    Args:
        conversation_id: The conversation identifier
        user_id: The user identifier from Entra ID (required - passed as query parameter)
        limit: Maximum number of messages to return (default: 50, max: 100)
        offset: Number of messages to skip (default: 0, for pagination)
    
    Returns:
        dict with paginated messages and metadata
    """
    try:
        if limit < 1 or limit > 100:
            limit = 50
        if offset < 0:
            offset = 0

        user_id = token_claims.get("oid") or token_claims.get("sub")
        cosmos_db_helper = CosmosDBHelper()
        all_history = cosmos_db_helper.get_conversation(user_id, conversation_id)
        total_count = len(all_history)
        
        all_history_sorted = sorted(
            all_history, 
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )
        
        paginated_history = all_history_sorted[offset:offset + limit]
        has_more = (offset + limit) < total_count
        
        logger.info(
            "Retrieved paginated conversation history",
            properties={
                "conversation_id": conversation_id,
                "total_count": total_count,
                "offset": offset,
                "has_more": has_more
            }
        )
        
        messages = [
            {
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": msg.get("timestamp"),
                "id": msg.get("id")
            }
            for msg in reversed(paginated_history)
        ]
        
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(
            "Error retrieving conversation history",
            exception=e,
            properties={"conversation_id": conversation_id}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation history: {str(e)}"
        )

@app.post("/api/llm-response", response_model=LLMResponse)
async def get_llm_response(
    llm_request: LLMRequest,
    token_claims: dict = Depends(verify_token),
):
    """
    Search documents and generate an LLM response using Azure OpenAI.
    
    The endpoint:
    1. Searches Azure Search Index for relevant documents
    2. Passes documents as context to Azure OpenAI
    3. Returns the LLM-generated response with source documents
    
    Query examples:
    - "What are the spare parts requirements?"
    - "Tell me about the commissioning process"
    - "What is the factory acceptance testing procedure?"
    """
    try:
        user_id = token_claims.get("oid") or token_claims.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User identity not found in token")

        query = llm_request.query.strip()
        conversation_id = llm_request.conversationId

        # Build request with authenticated user_id from token
        authenticated_request = LLMRequest(
            query=query,
            conversationId=conversation_id,
            user_id=user_id,
        )
        
        # Log LLM request
        logger.info(
            "LLM response requested",
            properties={
                "conversation_id": conversation_id,
                "query_preview": query[:100]
            }
        )
        
        if not query:
            logger.warning(
                "Empty query received",
                properties={"conversation_id": conversation_id}
            )
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty"
            )

        result = generate_response_from_query_with_history(authenticated_request)
        
        # Log LLM response success
        logger.info(
            "LLM response generated successfully",
            properties={
                "conversation_id": conversation_id,
                "documents_used": result.get("documents_used", 0)
            },
            measurements={
                "prompt_tokens": result.get("token_usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("token_usage", {}).get("completion_tokens", 0),
                "total_tokens": result.get("token_usage", {}).get("total_tokens", 0)
            }
        )

        logger.info(
            "LLM request completed successfully",
            properties={"conversation_id": conversation_id}
        )
        
        return LLMResponse(
            query=query,
            llm_response=result["llm_response"],
            documents_used=result["documents_used"],
            documents=[DocumentReference(**doc) for doc in result["documents"]],
            token_usage=TokenUsage(**result["token_usage"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error generating LLM response",
            exception=e,
            properties={"error_type": type(e).__name__}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error generating LLM response: {str(e)}"
        )

@app.get("/")
async def root():
    """Root endpoint - returns API information."""
    return {
        "message": "KnowBot Search API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search - Search documents in Azure Search",
            "llm_response": "POST /api/llm-response - Get LLM response with document context",
            "health": "GET /api/health - Health check"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_search_api:app",
        host="0.0.0.0",
        port=3001,
        reload=True
    )
