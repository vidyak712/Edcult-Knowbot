"""
Diagnostic script to check Azure Search index contents
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = "index-knowbot-new"
API_VERSION = "2023-11-01"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SEARCH_ADMIN_KEY
}

def check_index_stats():
    """Get index statistics"""
    try:
        url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/stats?api-version={API_VERSION}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        stats = response.json()
        print("\n=== Index Statistics ===")
        print(f"Document Count: {stats.get('documentCount', 0)}")
        print(f"Storage Size (bytes): {stats.get('storageSize', 0)}")
        return stats
    except Exception as e:
        print(f"[ERROR] Failed to get index stats: {e}")
        return None

def list_all_documents(top=10):
    """List all documents in the index"""
    try:
        url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs?api-version={API_VERSION}&$top={top}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        docs = response.json()
        
        print(f"\n=== First {top} Documents ===")
        total = docs.get('@odata.count', 0)
        print(f"Total Documents: {total}\n")
        
        for i, doc in enumerate(docs.get('value', []), 1):
            print(f"Doc {i}:")
            print(f"  ID: {doc.get('id')}")
            print(f"  Filename: {doc.get('filename', 'N/A')}")
            print(f"  Content Preview: {doc.get('content', '')[:100]}...")
            print()
        
        return total
    except Exception as e:
        print(f"[ERROR] Failed to list documents: {e}")
        return 0

def simple_text_search(query):
    """Perform simple text search (not vector)"""
    try:
        url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
        payload = {
            "search": query,
            "top": 5,
            "queryType": "simple"
        }
        
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        results = response.json()
        
        print(f"\n=== Text Search Results for '{query}' ===")
        matches = results.get('value', [])
        print(f"Matches Found: {len(matches)}\n")
        
        for i, doc in enumerate(matches, 1):
            print(f"Result {i}:")
            print(f"  ID: {doc.get('id')}")
            print(f"  Filename: {doc.get('filename', 'N/A')}")
            print(f"  Score: {doc.get('@search.score')}")
            print(f"  Preview: {doc.get('content', '')[:100]}...")
            print()
        
        return len(matches)
    except Exception as e:
        print(f"[ERROR] Failed text search: {e}")
        return 0

if __name__ == "__main__":
    print("Azure Search Index Diagnostic Tool")
    print("=" * 50)
    
    # Check if index exists and has data
    stats = check_index_stats()
    
    if stats and stats.get('documentCount', 0) == 0:
        print("\n⚠️  ERROR: Index is EMPTY - No documents have been indexed!")
        print("Action: Upload documents to Azure Search using:")
        print("  - Azure Portal Data Import wizard")
        print("  - Azure Search REST API")
        print("  - Python SDK with bulk operations")
    else:
        print(f"\n✅ Index has documents ({stats.get('documentCount', 0)} total)")
        
        # List sample documents
        total = list_all_documents(top=5)
        
        # Try searches
        print("\n" + "="*50)
        print("Testing Search Queries:")
        print("="*50)
        
        search_queries = [
            "Site and Environmental Conditions",
            "environmental",
            "site",
            "conditions",
            "commissioning"
        ]
        
        for query in search_queries:
            matches = simple_text_search(query)
