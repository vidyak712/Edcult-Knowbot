"""
Azure LLM Handler - Retrieve documents from Azure Search and generate LLM responses
"""
import os
import json
import requests
import re
import tiktoken
from html.parser import HTMLParser
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.app_insights_logger import get_logger

load_dotenv()

# Get logger
logger = get_logger("AzureLLMHandler")

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

SEARCH_INDEX_NAME = "index-knowbot"


def search_azure_index(query, top=4):
    """
    Search Azure Search Index and return documents
    """
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_ADMIN_KEY,
    }
    
    search_url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX_NAME}/docs/search?api-version=2023-11-01"
    
    search_payload = {
        "search": query,
        "top": top
    }
    
    try:
        logger.info(
            f"Searching Azure Index for: {query[:100]}",
            properties={
                "query": query,
                "top_docs": top,
                "index": SEARCH_INDEX_NAME
            }
        )
        
        response = requests.post(search_url, headers=headers, json=search_payload)
        response.raise_for_status()
        
        result = response.json()
        doc_count = len(result.get('value', []))
        
        logger.info(
            f"Azure Search found {doc_count} documents",
            properties={"query": query},
            measurements={"documents_found": doc_count}
        )
        
        return result
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error searching Azure Index for query: {query}",
            exception=e,
            properties={"query": query, "index": SEARCH_INDEX_NAME}
        )
        return {"value": []}


def html_table_to_markdown(html_content):
    """
    Convert HTML table to Markdown table format
    """
    # Extract table from HTML
    table_match = re.search(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL | re.IGNORECASE)
    if not table_match:
        return html_content
    
    table_html = table_match.group(1)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
    
    if not rows:
        return html_content
    
    markdown_rows = []
    for i, row in enumerate(rows):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL | re.IGNORECASE)
        # Clean cell content
        cleaned_cells = []
        for cell in cells:
            # Remove HTML tags and collapse whitespace
            clean = re.sub(r'<[^>]+>', '', cell)
            clean = re.sub(r'\s+', ' ', clean).strip()
            cleaned_cells.append(clean)
        
        if cleaned_cells:
            markdown_rows.append('| ' + ' | '.join(cleaned_cells) + ' |')
        
        # Add separator after first row (header)
        if i == 0:
            separator = '| ' + ' | '.join(['---'] * len(cleaned_cells)) + ' |'
            markdown_rows.append(separator)
    
    return '\n'.join(markdown_rows) if markdown_rows else html_content


def prepare_context_from_documents(documents):
    """
    Prepare context string from retrieved documents for LLM.
    Converts HTML tables to Markdown format.
    """
    context_parts = []
    for doc in documents:
        content = doc.get("content", "")
        filename = doc.get("filename", "Unknown")
        page_num = doc.get("page_number", "N/A")
        
        # Check if content is HTML table
        if '<table' in content.lower():
            # Convert HTML table to Markdown
            content = html_table_to_markdown(content)
        
        # Truncate very long content
        if len(content) > 2000:
            content = content[:2000] + "..."
        
        context_parts.append(f"[Source: {filename} (Page {page_num})]\n{content}")
    
    return "\n\n---\n\n".join(context_parts)


def count_tokens(text):
    """
    Count the number of tokens in the given text using tiktoken.
    Uses the encoding for GPT-4 (cl100k_base).
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        print(f"Error counting tokens: {e}")
        # Fallback: estimate 1 token per 4 characters
        return len(text) // 4


def prepare_context_with_token_limit(documents, max_tokens=4000):
    """
    Prepare context from documents while respecting token limit.
    Removes documents with lowest search score if total tokens exceed max_tokens.
    
    Args:
        documents: List of documents from Azure Search
        max_tokens: Maximum tokens allowed for context (default 4000)
    
    Returns:
        Tuple of (context_string, documents_used)
    """
    # Start with all documents
    remaining_docs = documents.copy()
    initial_doc_count = len(remaining_docs)
    
    logger.info(
        f"Preparing context with token limit",
        properties={
            "initial_documents": initial_doc_count,
            "max_tokens": max_tokens
        }
    )
    
    while remaining_docs:
        context = prepare_context_from_documents(remaining_docs)
        token_count = count_tokens(context)
        
        logger.info(
            f"Token check: {len(remaining_docs)} documents, {token_count} tokens",
            measurements={
                "document_count": len(remaining_docs),
                "token_count": token_count
            }
        )
        
        # If under limit, return
        if token_count <= max_tokens:
            logger.info(
                f"Context ready with {len(remaining_docs)} documents under token limit",
                properties={
                    "final_documents": len(remaining_docs),
                    "documents_removed": initial_doc_count - len(remaining_docs)
                },
                measurements={"final_token_count": token_count}
            )
            return context, remaining_docs
        
        # Find document with lowest search score and remove it
        # Default score to infinity if not present, so those documents are removed first
        min_score_doc = None
        min_score_idx = -1
        min_score = float('inf')
        
        for idx, doc in enumerate(remaining_docs):
            score = doc.get('@search.score', 0)
            if score < min_score:
                min_score = score
                min_score_doc = doc
                min_score_idx = idx
        
        if min_score_idx >= 0:
            removed_doc = remaining_docs.pop(min_score_idx)
            logger.warning(
                f"Removed low-scoring document to stay within token limit",
                properties={
                    "filename": removed_doc.get('filename', 'Unknown'),
                    "search_score": f"{min_score:.4f}",
                    "reason": "exceeded_token_limit"
                },
                measurements={
                    "removed_score": min_score,
                    "remaining_documents": len(remaining_docs)
                }
            )
        else:
            # Fallback: remove first if no score found
            removed_doc = remaining_docs.pop(0)
            logger.warning(
                f"Removed document (no score) to stay within token limit",
                properties={
                    "filename": removed_doc.get('filename', 'Unknown'),
                    "reason": "exceeded_token_limit_no_score"
                }
            )
    
    # If all documents removed, return empty context
    logger.warning(
        "All documents removed while respecting token limit",
        properties={"initial_documents": initial_doc_count}
    )
    return "", []


def trim_history_by_tokens(history, max_tokens=2000):
    """
    Trim conversation history to stay within token limit.
    Removes oldest messages first while respecting token limit.
    
    Args:
        history: List of conversation messages [{"role": "user"/"assistant", "content": "..."}, ...]
        max_tokens: Maximum tokens allowed for history (default 2000)
    
    Returns:
        Trimmed history list
    """
    if not history:
        return history
    
    # Convert history to text and count tokens
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    token_count = count_tokens(history_text)
    
    print(f"[HISTORY TOKEN CHECK] Messages: {len(history)}, Tokens: {token_count}")
    
    # If within limit, return as is
    if token_count <= max_tokens:
        return history
    
    # Remove oldest messages (pairs of user-assistant) until within limit
    remaining_history = history.copy()
    initial_msg_count = len(remaining_history)
    
    logger.info(
        f"Trimming history to token limit",
        properties={"initial_messages": initial_msg_count, "max_tokens": max_tokens}
    )
    
    while remaining_history:
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in remaining_history])
        token_count = count_tokens(history_text)
        
        logger.info(
            f"History token check: {len(remaining_history)} messages, {token_count} tokens",
            measurements={
                "message_count": len(remaining_history),
                "token_count": token_count
            }
        )
        
        if token_count <= max_tokens:
            messages_removed = initial_msg_count - len(remaining_history)
            if messages_removed > 0:
                logger.info(
                    f"History trimmed: removed {messages_removed} messages",
                    properties={"messages_removed": messages_removed},
                    measurements={"final_token_count": token_count}
                )
            return remaining_history
        
        # Remove oldest message (first one) and try again
        removed_msg = remaining_history.pop(0)
        removed_role = removed_msg.get("role", "unknown")
        removed_preview = removed_msg.get("content", "")[:50]
        logger.warning(
            f"Removed oldest {removed_role} message to stay within token limit",
            properties={
                "role": removed_role,
                "preview": removed_preview,
                "remaining_messages": len(remaining_history)
            }
        )
    
    # If all messages removed, return empty list
    logger.warning(
        f"Removed all history messages to stay within {max_tokens} tokens",
        properties={"initial_messages": initial_msg_count}
    )
    return []


def call_azure_openai(query, documents, history=None):
    """
    Call Azure OpenAI with the query and document context using LangChain
    Optionally includes conversation history for multi-turn conversations
    
    Args:
        query: The user's question
        documents: List of documents from Azure Search (token-aware filtering applied)
        history: Conversation history (will be trimmed to 2k tokens max)
    
    Returns:
        Tuple of (response_content, token_usage_dict, documents_used)
    """
    
    # Prepare context with token limit checking (max 4000 tokens)
    documents_context, filtered_docs = prepare_context_with_token_limit(documents, max_tokens=4000)
    
    # Trim history to stay within 2k tokens
    trimmed_history = trim_history_by_tokens(history, max_tokens=2000) if history else None
    
    if not documents_context:
        return "No relevant documents found for your query.", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, 0
    
    # Initialize Azure OpenAI Chat client using LangChain
    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
        temperature=0.3,
        max_tokens=1500,
        top_p=0.95,
        timeout=60
    )
    
    # Check if user is asking for table format
    query_lower = query.lower()
    request_table = any(keyword in query_lower for keyword in ['table', 'format as table', 'show as table', 'as table', 'table format'])
    
    # Prepare the system prompt
    if request_table:
        system_prompt = """You are a helpful assistant that answers questions based on provided document content. 
        Answer the user's question using only the information from the provided documents.
    
        IMPORTANT FORMATTING INSTRUCTIONS:
        - Format your response as a proper Markdown table with clear columns
        - Markdown table format example:
        | Column 1 | Column 2 | Column 3 |
        |----------|----------|----------|
        | Value 1  | Value 2  | Value 3  |
        - Use the pipe (|) separator with proper row separators (|---|)
        - Keep formatting clean and readable

        If the answer is not in the documents, say so clearly."""
        
        user_message = f"""Based on the following documents, please answer this question:

        QUESTION: {query}

        DOCUMENTS:
        {documents_context}

        Please provide the answer formatted as a Markdown table. Include relevant columns and organize the information clearly."""
    else:
        system_prompt = """You are a helpful assistant that answers questions based on provided document content. 
        Answer the user's question using only the information from the provided documents.

        FORMATTING INSTRUCTIONS:
        - Preserve the original document format (paragraphs, sections, structure)
        - Do NOT convert to bullet points or lists unless the source document uses them
        - Maintain readability while keeping the original formatting intact
        - Do NOT format as a table unless explicitly asked

        If the answer is not in the documents, say so clearly."""
        
        user_message = f"""Based on the following documents, please answer this question:

        QUESTION: {query}

        DOCUMENTS:
        {documents_context}

        Please provide the answer while preserving the original document format and structure. Do not reformat paragraphs into bullet points."""

    # Build message list using LangChain message classes
    messages = [SystemMessage(content=system_prompt)]
    
    # Add trimmed conversation history if provided
    if trimmed_history:
        logger.info(
            f"Using trimmed conversation history",
            properties={"history_message_count": len(trimmed_history)}
        )
        for msg in trimmed_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
    elif history:
        logger.warning(
            "Original conversation history had messages but was trimmed to 0",
            properties={"original_message_count": len(history)}
        )
    
    # Always add the current user message with proper formatting instructions
    messages.append(HumanMessage(content=user_message))
    
    try:
        # Log LLM invocation
        logger.info(
            "Invoking Azure OpenAI LLM",
            properties={
                "deployment": AZURE_OPENAI_DEPLOYMENT_NAME,
                "table_request": request_table,
                "total_messages": len(messages)
            }
        )
        
        # Call the LLM using LangChain
        response = llm.invoke(messages)
        
        # Extract token usage information
        token_usage = {
            "prompt_tokens": getattr(response, 'response_metadata', {}).get('token_usage', {}).get('prompt_tokens', 0),
            "completion_tokens": getattr(response, 'response_metadata', {}).get('token_usage', {}).get('completion_tokens', 0),
            "total_tokens": getattr(response, 'response_metadata', {}).get('token_usage', {}).get('total_tokens', 0)
        }
        
        # Log successful response
        logger.info(
            "Azure OpenAI LLM response received successfully",
            properties={
                "deployment": AZURE_OPENAI_DEPLOYMENT_NAME,
                "documents_used": len(filtered_docs)
            },
            measurements={
                "prompt_tokens": token_usage["prompt_tokens"],
                "completion_tokens": token_usage["completion_tokens"],
                "total_tokens": token_usage["total_tokens"],
                "response_length": len(response.content)
            }
        )
        
        return response.content, token_usage, len(filtered_docs)
            
    except Exception as e:
        logger.error(
            "Error calling Azure OpenAI LLM",
            exception=e,
            properties={
                "deployment": AZURE_OPENAI_DEPLOYMENT_NAME,
                "query_preview": query[:100]
            }
        )
        error_msg = f"Error generating response: {str(e)}"
        return error_msg, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, len(filtered_docs)


def generate_response_from_query(query, top_docs=4):
    """
    Main function: Search documents and generate LLM response
    """
    # Step 1: Search Azure Search Index
    search_results = search_azure_index(query, top=top_docs)
    documents = search_results.get("value", [])
    
    if not documents:
        return {
            "query": query,
            "llm_response": "No relevant documents found for your query.",
            "documents_used": 0,
            "documents": [],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    # Step 2: Call Azure OpenAI with documents (token checking happens inside)
    llm_response, token_usage, docs_used = call_azure_openai(query, documents)
    
    # Step 3: Return formatted response
    return {
        "query": query,
        "llm_response": llm_response,
        "documents_used": docs_used,
        "documents": [
            {
                "id": doc.get("id"),
                "filename": doc.get("filename"),
                "page_number": doc.get("page_number"),
                "preview": doc.get("content", "")[:200] + "..." if len(doc.get("content", "")) > 200 else doc.get("content", "")
            }
            for doc in documents[:docs_used]  # Only include documents that were actually used
        ],
        "token_usage": token_usage
    }

def generate_response_from_query_with_history(query, history=None, top_docs=4):
    """
    Main function: Search documents and generate LLM response with conversation history
    
    Args:
        query: The user's current query
        history: List of previous messages with format [{"role": "user"/"assistant", "content": "..."}, ...]
        top_docs: Number of documents to retrieve
    """
    # Step 1: Search Azure Search Index
    search_results = search_azure_index(query, top=top_docs)
    documents = search_results.get("value", [])
    
    if not documents:
        return {
            "query": query,
            "llm_response": "No relevant documents found for your query.",
            "documents_used": 0,
            "documents": [],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    # Step 2: Call Azure OpenAI with documents and history (token checking happens inside)
    llm_response, token_usage, docs_used = call_azure_openai(query, documents, history=history)
    
    # Step 3: Return formatted response
    return {
        "query": query,
        "llm_response": llm_response,
        "documents_used": docs_used,
        "documents": [
            {
                "id": doc.get("id"),
                "filename": doc.get("filename"),
                "page_number": doc.get("page_number"),
                "preview": doc.get("content", "")[:200] + "..." if len(doc.get("content", "")) > 200 else doc.get("content", "")
            }
            for doc in documents[:docs_used]  # Only include documents that were actually used
        ],
        "token_usage": token_usage
    }


def generate_response_from_documents_with_history(query, documents, history=None):
    """
    Generate LLM response using pre-retrieved documents and conversation history.
    This avoids redundant Azure Search calls when documents are already retrieved.
    Token-aware filtering is applied to the documents context.
    
    Args:
        query: The user's current query
        documents: List of pre-retrieved documents from Azure Search
        history: List of previous messages with format [{"role": "user"/"assistant", "content": "..."}, ...]
    
    Returns:
        Dictionary with llm_response, documents_used, documents list, and token_usage
    """
    if not documents:
        return {
            "query": query,
            "llm_response": "No relevant documents found for your query.",
            "documents_used": 0,
            "documents": [],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    # Call Azure OpenAI with documents and history (token checking happens inside)
    llm_response, token_usage, docs_used = call_azure_openai(query, documents, history=history)
    
    # Return formatted response
    return {
        "query": query,
        "llm_response": llm_response,
        "documents_used": docs_used,
        "documents": [
            {
                "id": doc.get("id"),
                "filename": doc.get("filename"),
                "page_number": doc.get("page_number"),
                "preview": doc.get("content", "")[:200] + "..." if len(doc.get("content", "")) > 200 else doc.get("content", "")
            }
            for doc in documents[:docs_used]  # Only include documents that were actually used
        ],
        "token_usage": token_usage
    }

if __name__ == "__main__":
    # Test the handler
    test_query = "What are the spare parts requirements?"
    result = generate_response_from_query(test_query, top_docs=5)
    print(json.dumps(result, indent=2))
