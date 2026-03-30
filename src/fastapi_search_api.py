import os
import sys
from pathlib import Path

# Add parent directory to path to handle imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
from dotenv import load_dotenv
from datetime import datetime
from langchain_openai import AzureOpenAIEmbeddings

# Import helpers
from helpers.cosmosDBHelper import CosmosDBHelper
from helpers.app_insights_logger import get_logger

try:
    from src.azure_llm_handler import generate_response_from_query, generate_response_from_query_with_history, generate_response_from_documents_with_history
except ImportError:
    from azure_llm_handler import generate_response_from_query, generate_response_from_query_with_history, generate_response_from_documents_with_history

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger("FastAPISearchAPI")

# Initialize Azure OpenAI Embeddings for vector search
embeddings = AzureOpenAIEmbeddings(
    api_key=os.getenv("AZURE_OPENAI_EMBED_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_EMBED_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_EMBED_ENDPOINT"),
    model=os.getenv("AZURE_OPENAI_EMBED_MODEL_NAME")
)

# Initialize FastAPI app
app = FastAPI(
    title="KnowBot Search API",
    description="Azure AI Search API for KnowBot",
    version="1.0.0"
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
INDEX_NAME = "index-knowbot"
API_VERSION = "2023-11-01"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SEARCH_ADMIN_KEY
}

# Pydantic models
class SearchRequest(BaseModel):
    query: str
    conversationId : str
    top: int = 4
    skip: int = 0

class SearchResult(BaseModel):
    id: str
    content: str
    filename: Optional[str] = None
    page_number: Optional[int] = None
    indexed_date: Optional[str] = None
    text_length: Optional[int] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    count: int
    total: int

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
    user_id: str  # From Entra ID authentication
    top_docs: int = 4

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

@app.post("/api/search", response_model=SearchResponse)
async def search(search_request: SearchRequest):
    """
    Search documents in Azure Search index.
    
    Query examples:
    - "API 617" - Search for API standards
    - "performance" - Search for performance documents
    - "revision" - Search for revision information
    """
    try:
        query = search_request.query.strip()
        conversation_id = search_request.conversationId
        top = search_request.top
        skip = search_request.skip
        
        # Log the conversation context
        print(f"[CONVERSATION {conversation_id}] Search query: {query}")
        
        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty"
            )
        
        if top > 100:
            top = 100  # Limit max results to 100
        
        # Build Azure Search query with vector search
        search_url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
        
        # Generate embedding for the query
        try:
            query_embedding = embeddings.embed_query(query)
            print(f"[CONVERSATION {conversation_id}] Embedding generated successfully")
        except Exception as e:
            print(f"[ERROR] Failed to generate embedding for query: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate query embedding: {str(e)}"
            )
        
        search_payload = {
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_embedding,
                    "k": top,
                    "fields": "vectorContent"
                }
            ],
            "top": top,
            "skip": skip
        }
        
        print(f"[CONVERSATION {conversation_id}] Vector search payload: top={top}, skip={skip}")
        
        # Call Azure Search
        response = requests.post(search_url, headers=HEADERS, json=search_payload)
        
        if response.status_code != 200:
            print(f"[ERROR] Status: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
        
        response.raise_for_status()
        
        result = response.json()
        
        # Format results
        formatted_results = []
        for doc in result.get('value', []):
            formatted_results.append(SearchResult(
                id=doc.get('id'),
                content=doc.get('content', ''),
                filename=doc.get('filename'),
                page_number=doc.get('page_number'),
                indexed_date=doc.get('indexed_date'),
                text_length=doc.get('text_length', len(doc.get('content', '')))
            ))
        
        return SearchResponse(
            results=formatted_results,
            count=len(formatted_results),
            total=result.get('@odata.count', len(formatted_results))
        )
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Azure Search error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )

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

@app.get("/api/conversation-history/{conversation_id}")
async def get_conversation_history(conversation_id: str, user_id: str, limit: int = 50, offset: int = 0):
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
async def get_llm_response(llm_request: LLMRequest):
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
        query = llm_request.query.strip()
        conversation_id = llm_request.conversationId
        user_id = llm_request.user_id  # From Entra ID
        top_docs = llm_request.top_docs
        
        # Log LLM request
        logger.info(
            "LLM response requested",
            properties={
                "conversation_id": conversation_id,
                "query_preview": query[:100],
                "top_docs": top_docs
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
        
        if top_docs < 1 or top_docs > 20:
            top_docs = 4  # Default to 4 documents
        
        # Search for relevant documents in Azure Search using vector search
        search_url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
        
        # Generate embedding for the query
        try:
            query_embedding = embeddings.embed_query(query)
            logger.info(
                "Query embedding generated",
                properties={"conversation_id": conversation_id}
            )
        except Exception as e:
            logger.error(
                "Failed to generate query embedding",
                exception=e,
                properties={"conversation_id": conversation_id}
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate query embedding: {str(e)}"
            )
        
        search_payload = {
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_embedding,
                    "k": top_docs,
                    "fields": "vectorContent"
                }
            ],
            "top": top_docs
        }
        
        logger.info(
            "Searching Azure Search Index with vector search",
            properties={
                "conversation_id": conversation_id,
                "query": query,
                "top_docs": top_docs,
                "index": INDEX_NAME
            }
        )
        
        search_response = requests.post(search_url, headers=HEADERS, json=search_payload)
        
        # Error handling
        if search_response.status_code != 200:
            logger.error(
                "Azure Search returned error",
                properties={
                    "conversation_id": conversation_id,
                    "status_code": search_response.status_code,
                    "response": search_response.text[:200]
                }
            )
        
        search_response.raise_for_status()
        search_result = search_response.json()
        
        documents = search_result.get('value', [])
        logger.info(
            f"Azure Search found documents",
            properties={
                "conversation_id": conversation_id,
                "document_count": len(documents)
            },
            measurements={"documents_found": len(documents)}
        )
        
        # Initialize Cosmos DB helper and retrieve conversation history
        user_id = "user_001@edcults.com"  # Get from authenticated user in production
        history = cosmos_db_helper.get_last_messages(user_id, conversation_id)
        
        logger.info(
            "Retrieved conversation history",
            properties={
                "conversation_id": conversation_id,
                "history_message_count": len(history)
            }
        )

        # Append current user query to history
        history.append({
            "role": "user",
            "content": query
        })

        # Send pre-retrieved documents and conversation history to LLM handler
        # This avoids redundant Azure Search calls
        logger.info(
            "Generating LLM response",
            properties={
                "conversation_id": conversation_id,
                "documents_count": len(documents),
                "history_count": len(history)
            }
        )
        
        result = generate_response_from_documents_with_history(query, documents=documents, history=history)
        
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

        # Store the exchange in Cosmos DB for future context
        try:
            #add the user message 
            cosmos_db_helper.add_record(
                user_id="user_001@edcults.com",
                conversauser_id,
                conversation_id=conversation_id,
                role="user",
                content=query
            )

            #add the assistant message 
            cosmos_db_helper.add_record(
                user_id=user_idd,
                role="assistant",
                content=result["llm_response"]
            )
            
            logger.info(
                "Conversation stored in Cosmos DB",
                properties={"conversation_id": conversation_id}
            )
        except Exception as cosmos_error:
            logger.warning(
                "Failed to store messages in Cosmos DB",
                exception=cosmos_error,
                properties={"conversation_id": conversation_id}
            )
            # Continue without storing - don't fail the response

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

@app.get("/docs", include_in_schema=False)
async def get_docs():
    """Auto-generated API documentation."""
    pass

def build_messages(conversation_id, user_message, user_id="user_001@edcults.com"):

    cosmos_db_helper = CosmosDBHelper()
    history = cosmos_db_helper.get_last_messages(user_id, conversation_id)

    history.append({
        "role": "user",
        "content": user_message
    })

    return history
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_search_api:app",
        host="0.0.0.0",
        port=3001,
        reload=True
    )
