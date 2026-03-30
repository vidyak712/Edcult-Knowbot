import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings

# Load environment variables
load_dotenv()

class AzureIndexHandler:
    def __init__(self):
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.index_name = "index-knowbot"
        self.api_version = "2023-11-01"
        self.headers = {
            "Content-Type": "application/json",
            "api-key": self.admin_key
        }
        
        # Paths
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.text_dir = os.path.join(self.project_root, "output", "extracted_content", "text")
        self.html_dir = os.path.join(self.project_root, "output", "extracted_content", "html")
        self.schema_fields = {}
        
        # Initialize Azure OpenAI Embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            api_key=os.getenv("AZURE_OPENAI_EMBED_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_EMBED_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_EMBED_ENDPOINT"),
            model=os.getenv("AZURE_OPENAI_EMBED_MODEL_NAME")
        )

    def get_index_schema(self) -> bool:
        """Fetch and parse the index schema to determine available fields."""
        url = f"{self.search_endpoint}/indexes/{self.index_name}?api-version={self.api_version}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            schema = response.json()
            
            # Extract field names and types
            for field in schema.get("fields", []):
                self.schema_fields[field["name"]] = field.get("type", "Edm.String")
            
            print(f"[OK] Index schema retrieved. Available fields: {', '.join(self.schema_fields.keys())}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Error getting index schema: {e}")
            return False

    def prepare_document(self, base_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Filter document to only include fields that exist in the schema."""
        filtered_doc = {}
        
        for field_name in self.schema_fields.keys():
            if field_name in base_doc:
                value = base_doc[field_name]
                # Format dates as ISO strings
                if isinstance(value, datetime):
                    value = value.isoformat()
                filtered_doc[field_name] = value
            # Handle vectorContent field - convert list to proper format for Azure Search
            elif field_name == "vectorContent" and "vectorContent" in base_doc:
                filtered_doc[field_name] = base_doc["vectorContent"]
        
        return filtered_doc

    def chunk_text_by_paragraph(self, text: str, max_chunk_size: int = 2000) -> List[str]:
        """Split text by paragraphs using LangChain's RecursiveCharacterTextSplitter."""
        # Initialize LangChain text splitter
        # Splits on: paragraph breaks, sentences, words, then characters
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " ", ""],
            chunk_size=max_chunk_size,
            chunk_overlap=0,  # No overlap to avoid duplication
            length_function=len,
        )
        
        chunks = splitter.split_text(text)
        return [c.strip() for c in chunks if c.strip()]

    def process_text_files(self) -> List[Dict[str, Any]]:
        """Process text files and chunk by paragraph."""
        documents = []
        text_files = sorted(Path(self.text_dir).glob("*.txt"))
        
        for file_path in text_files:
            # Extract page number from filename
            match = re.search(r'page_(\d+)', file_path.stem)
            if not match:
                continue
            
            page_num = int(match.group(1))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            # Chunk by paragraph
            chunks = self.chunk_text_by_paragraph(text_content)
            
            for chunk_idx, chunk in enumerate(chunks):
                if chunk.strip():
                    doc_id = f"text_page_{page_num}_chunk_{chunk_idx + 1}"
                    
                    # Calculate embedding for the chunk content
                    try:
                        embedding = self.embeddings.embed_query(chunk)
                    except Exception as e:
                        print(f"[WARNING] Failed to generate embedding for {doc_id}: {e}")
                        embedding = None
                    
                    base_doc = {
                        "id": doc_id,
                        "content": chunk,
                        "filename": file_path.name,
                        "page_number": page_num,
                        "indexed_date": datetime.now(timezone.utc),
                        "text_length": len(chunk),
                        "vectorContent": embedding,
                    }
                    
                    filtered_doc = self.prepare_document(base_doc)
                    if "id" in filtered_doc:  # Ensure id is always present
                        documents.append(filtered_doc)
        
        return documents

    def process_html_files(self) -> List[Dict[str, Any]]:
        """Process markdown table files as single chunks - store entire markdown content."""
        documents = []
        html_files = sorted(Path(self.html_dir).glob("*.md"))
        
        for file_path in html_files:
            # Extract page number from filename
            match = re.search(r'page_(\d+)', file_path.stem)
            if not match:
                continue
            
            page_num = int(match.group(1))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            if md_content:
                doc_id = f"html_page_{page_num}_table_1"
                
                # Note: Using zero vector for tables (structured data, not optimal for semantic search)
                # Get embedding dimension from a text chunk if possible, otherwise use standard 1536 for text-embedding-3-small
                zero_vector = [0.0] * 1536
                
                base_doc = {
                    "id": doc_id,
                    "content": md_content,  # Store markdown table as content
                    "filename": file_path.name,
                    "page_number": page_num,
                    "indexed_date": datetime.now(timezone.utc),
                    "text_length": len(md_content),
                    "vectorContent": zero_vector,  # Zero vector for tables
                }
                
                filtered_doc = self.prepare_document(base_doc)
                if "id" in filtered_doc:  # Ensure id is always present
                    documents.append(filtered_doc)
        
        return documents

    def upload_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Upload documents to Azure Search index."""
        if not documents:
            print("No documents to upload")
            return True
        
        url = f"{self.search_endpoint}/indexes/{self.index_name}/docs/index?api-version={self.api_version}"
        
        # Batch upload
        payload = {
            "value": [
                {
                    "@search.action": "upload",
                    **doc
                }
                for doc in documents
            ]
        }
        
        try:
            print(f"Batch payload: {json.dumps(payload['value'][0], indent=2, default=str)}")
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            succeeded = sum(1 for r in result['value'] if r.get('status'))
            failed = sum(1 for r in result['value'] if not r.get('status'))
            
            print(f"[OK] Batch upload completed")
            print(f"  Success: {succeeded}/{len(documents)}")
            if failed > 0:
                print(f"  Failed: {failed}")
            
            # Print errors if any
            for item in result['value']:
                if not item.get('status'):
                    print(f"  Error in {item.get('key')}: {json.dumps(item, indent=2, default=str)}")
            
            return failed == 0
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Error uploading documents: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Response: {e.response.text}")
            return False

    def run(self):
        """Process and index all documents."""
        print("\n" + "="*60)
        print("Azure Index Handler - Processing and Indexing Documents")
        print("="*60)
        
        # Get index schema
        print("\n[1/4] Fetching index schema...")
        if not self.get_index_schema():
            print("[ERROR] Failed to get index schema. Cannot proceed.")
            return
        
        # Process text files
        print("\n[2/4] Processing text files (chunking by paragraph)...")
        text_documents = self.process_text_files()
        print(f"  [OK] Processed {len(text_documents)} text chunks")
        
        # Process HTML files
        print("\n[3/4] Processing markdown table files...")
        html_documents = self.process_html_files()
        print(f"  [OK] Processed {len(html_documents)} HTML chunks")
        
        # Combine documents
        all_documents = text_documents + html_documents
        
        # Upload to Azure Search
        print(f"\n[4/4] Uploading {len(all_documents)} documents to Azure Search index '{self.index_name}'...")
        success = self.upload_documents(all_documents)
        
        if success:
            print("\n" + "="*60)
            print("[SUCCESS] Indexing Complete!")
            print("="*60)
            print(f"  Total documents indexed: {len(all_documents)}")
            print(f"  Text chunks: {len(text_documents)}")
            print(f"  Markdown table chunks: {len(html_documents)}")
        else:
            print("\n[WARNING] Some documents failed to index")

def main():
    handler = AzureIndexHandler()
    handler.run()

if __name__ == "__main__":
    main()
