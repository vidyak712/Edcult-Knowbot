import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = "index-knowbot-new"
API_VERSION = "2023-11-01"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": ADMIN_KEY
}

INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        {
            "name": "id",
            "type": "Edm.String",
            "key": True,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "content",
            "type": "Edm.String",
            "key": False,
            "searchable": True,
            "filterable": False,
            "retrievable": True,
            "sortable": False,
            "analyzer": "en.microsoft"
        },
        {
            "name": "filename",
            "type": "Edm.String",
            "key": False,
            "searchable": True,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "page_number",
            "type": "Edm.Int32",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "indexed_date",
            "type": "Edm.DateTimeOffset",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "text_length",
            "type": "Edm.Int32",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        # --- New metadata fields ---
        {
            "name": "parent_section",
            "type": "Edm.String",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "section_number",
            "type": "Edm.String",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        {
            "name": "section_title",
            "type": "Edm.String",
            "key": False,
            "searchable": True,
            "filterable": False,
            "retrievable": True,
            "sortable": False
        },
        {
            "name": "chunk_type",
            "type": "Edm.String",
            "key": False,
            "searchable": False,
            "filterable": True,
            "retrievable": True,
            "sortable": True
        },
        # --- Vector field ---
        {
            "name": "vectorContent",
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "retrievable": False,
            "dimensions": 1536,
            "vectorSearchProfile": "hnsw-profile"
        }
    ],
    "vectorSearch": {
        "algorithms": [
            {
                "name": "hnsw-algo",
                "kind": "hnsw",
                "hnswParameters": {
                    "metric": "cosine",
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500
                }
            }
        ],
        "profiles": [
            {
                "name": "hnsw-profile",
                "algorithm": "hnsw-algo"
            }
        ]
    },
    "semantic": {
        "configurations": [
            {
                "name": "semantic-config",
                "prioritizedFields": {
                    "titleField": {"fieldName": "section_title"},
                    "prioritizedContentFields": [
                        {"fieldName": "content"}
                    ],
                    "prioritizedKeywordsFields": [
                        {"fieldName": "filename"}
                    ]
                }
            }
        ]
    }
}


def create_index() -> bool:
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}"

    try:
        response = requests.put(url, headers=HEADERS, json=INDEX_SCHEMA)
        response.raise_for_status()
        print(f"[OK] Index '{INDEX_NAME}' created successfully.")
        print(f"     Fields: {', '.join(f['name'] for f in INDEX_SCHEMA['fields'])}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP error creating index: {e}")
        print(f"        Response: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request error creating index: {e}")
        return False


def index_exists() -> bool:
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}"
    try:
        response = requests.get(url, headers=HEADERS)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def main():
    print("="*60)
    print(f"Azure AI Search - Index Creator")
    print(f"Index: {INDEX_NAME}")
    print("="*60)

    if not SEARCH_ENDPOINT or not ADMIN_KEY:
        print("[ERROR] AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_ADMIN_KEY not set in environment.")
        return

    if index_exists():
        print(f"[INFO] Index '{INDEX_NAME}' already exists.")       

    create_index()


if __name__ == "__main__":
    main()
