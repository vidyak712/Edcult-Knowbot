"""
Delete all documents from Azure Search Index
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
SEARCH_INDEX_NAME = "index-knowbot"

def delete_all_documents():
    """Delete all documents from the search index"""
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_ADMIN_KEY,
    }
    
    # Step 1: Get all document IDs
    search_url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX_NAME}/docs/search?api-version=2023-11-01"
    search_payload = {
        "search": "*",
        "top": 1000
    }
    
    try:
        response = requests.post(search_url, headers=headers, json=search_payload)
        response.raise_for_status()
        result = response.json()
        docs = result.get("value", [])
        
        if not docs:
            print("[INFO] Index is already empty!")
            return
        
        print(f"\n[1/2] Found {len(docs)} documents to delete...")
        
        # Step 2: Delete documents in batch
        delete_url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX_NAME}/docs/index?api-version=2023-11-01"
        delete_payload = {
            "value": [
                {"@search.action": "delete", "id": doc["id"]}
                for doc in docs
            ]
        }
        
        delete_response = requests.post(delete_url, headers=headers, json=delete_payload)
        delete_response.raise_for_status()
        delete_result = delete_response.json()
        
        successful = sum(1 for item in delete_result.get("value", []) if item.get("status") == True)
        print(f"[2/2] Deleted {successful}/{len(docs)} documents")
        
        print("\n[SUCCESS] Index cleared successfully!")
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to delete documents: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 80)
    print("Azure Search Index Deletion Tool")
    print("=" * 80)
    print(f"Index: {SEARCH_INDEX_NAME}")
    print(f"Endpoint: {AZURE_SEARCH_ENDPOINT}")
    print()
    
    delete_all_documents()
