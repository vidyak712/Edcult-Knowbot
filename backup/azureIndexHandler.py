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
        self.index_name = "index-knowbot-new"
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
                if isinstance(value, datetime):
                    value = value.isoformat()
                filtered_doc[field_name] = value
        
        return filtered_doc

    def chunk_by_subsection(self, text: str, max_chunk_size: int = 2000) -> List[Dict[str, Any]]:
        """Split text by section/subsection headings.

        Detects patterns:
          '1. INTRODUCTION AND PURPOSE'  (main section)
          '1.1 Background'               (subsection)

        Returns a list of dicts with content and metadata.
        """
        # Matches "1. TITLE IN CAPS" (main) and "1.1 Title Text" (subsection)
        # Pattern: digit(s), optional .digit(s), optional dot, 1-3 spaces, Capital letter + text
        heading_re = re.compile(
            r'^(\d+(?:\.\d+)?)\.?\s{1,3}([A-Z][^\n]{3,})$',
            re.MULTILINE
        )

        matches = list(heading_re.finditer(text))
        chunks = []

        # Text before the first heading (cover page / preamble)
        preamble_end = matches[0].start() if matches else len(text)
        preamble = text[:preamble_end].strip()
        if preamble:
            chunks.append({
                "content": preamble,
                "section_number": "",
                "section_title": "",
                "parent_section": "",
                "chunk_type": "header",
            })

        if not matches:
            return chunks

        for i, match in enumerate(matches):
            section_label = match.group(1)     # e.g. "4.3" or "4"
            title = match.group(2).strip()

            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            if not body:
                continue

            section_number = section_label
            parent_section = section_label.split(".")[0]   # "4.3" -> "4", "4" -> "4"
            chunk_type = "subsection"

            # Prepend heading so every chunk carries its own context
            content_with_heading = f"Section {section_number}: {title}\n\n{body}"

            # Secondary split if chunk exceeds max size
            if len(content_with_heading) > max_chunk_size:
                splitter = RecursiveCharacterTextSplitter(
                    separators=["\n\n", "\n", ". ", " ", ""],
                    chunk_size=max_chunk_size,
                    chunk_overlap=100,
                    length_function=len,
                )
                for sub in splitter.split_text(content_with_heading):
                    if sub.strip():
                        chunks.append({
                            "content": sub.strip(),
                            "section_number": section_number,
                            "section_title": title,
                            "parent_section": parent_section,
                            "chunk_type": chunk_type,
                        })
            else:
                chunks.append({
                    "content": content_with_heading,
                    "section_number": section_number,
                    "section_title": title,
                    "parent_section": parent_section,
                    "chunk_type": chunk_type,
                })

        return chunks

    def _last_heading_on_page(self, page_num: int):
        """Return (section_number, section_title, parent_section) for the last heading on a page."""
        text_file = Path(self.text_dir) / f"page_{page_num}_text.txt"
        if not text_file.exists():
            return "", "", ""
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        heading_re = re.compile(
            r'^(\d+(?:\.\d+)?)\.?\s{1,3}([A-Z][^\n]{3,})$',
            re.MULTILINE
        )
        matches = list(heading_re.finditer(text))
        if not matches:
            return "", "", ""
        m = matches[-1]
        label = m.group(1)
        return label, m.group(2).strip(), label.split(".")[0]

    def _get_table_section_mappings(self, page_num: int, num_tables: int) -> List[Dict[str, str]]:
        """Return one section-context dict per table on the page, matched by order.

        Strategy:
          - Split the text file into segments at each section heading.
          - Segments with content before the first heading use the last heading
            from the previous page (continuation table).
          - Each subsequent segment after a heading maps to that heading.
          - Result is trimmed / padded to exactly num_tables entries.
        """
        heading_re = re.compile(
            r'^(\d+(?:\.\d+)?)\.?\s{1,3}([A-Z][^\n]{3,})$',
            re.MULTILINE
        )

        text_file = Path(self.text_dir) / f"page_{page_num}_text.txt"
        empty = {"section_number": "", "section_title": "", "parent_section": ""}

        if not text_file.exists():
            return [empty] * num_tables

        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()

        lines = text.split("\n")

        # Collect headings with their starting line number
        headings = []
        for match in heading_re.finditer(text):
            line_num = text[:match.start()].count("\n")
            headings.append({
                "line": line_num,
                "section_number": match.group(1),
                "section_title": match.group(2).strip(),
                "parent_section": match.group(1).split(".")[0],
            })

        # Fallback context: last heading from the previous page
        prev_num, prev_title, prev_parent = self._last_heading_on_page(page_num - 1)
        fallback = {
            "section_number": prev_num,
            "section_title": prev_title,
            "parent_section": prev_parent,
        }

        heading_lines = [h["line"] for h in headings]
        segments = []

        # Pre-heading segment: lines before the first heading
        pre_end = heading_lines[0] if heading_lines else len(lines)
        pre_lines = lines[0:pre_end]
        # Only treat as a real table segment if there are meaningful content lines
        if sum(1 for line in pre_lines if line.strip()) > 2:
            segments.append(fallback)

        # One segment per heading
        for i, h in enumerate(headings):
            seg_end = heading_lines[i + 1] if i + 1 < len(heading_lines) else len(lines)
            seg_lines = lines[h["line"]:seg_end]
            if any(line.strip() for line in seg_lines):
                segments.append({
                    "section_number": h["section_number"],
                    "section_title": h["section_title"],
                    "parent_section": h["parent_section"],
                })

        # Pad to num_tables if fewer segments than tables
        while len(segments) < num_tables:
            segments.append(segments[-1] if segments else fallback)

        return segments[:num_tables]

    def process_text_files(self) -> List[Dict[str, Any]]:
        """Process text files and chunk by subsection."""
        documents = []
        text_files = sorted(Path(self.text_dir).glob("*.txt"))

        for file_path in text_files:
            match = re.search(r'page_(\d+)', file_path.stem)
            if not match:
                continue

            page_num = int(match.group(1))

            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()

            chunk_dicts = self.chunk_by_subsection(text_content)

            for chunk_idx, chunk_dict in enumerate(chunk_dicts):
                content = chunk_dict["content"]
                if not content.strip():
                    continue

                doc_id = f"text_page_{page_num}_chunk_{chunk_idx + 1}"

                try:
                    embedding = self.embeddings.embed_query(content)
                except Exception as e:
                    print(f"[WARNING] Failed to generate embedding for {doc_id}: {e}")
                    embedding = None

                base_doc = {
                    "id": doc_id,
                    "content": content,
                    "filename": file_path.name,
                    "page_number": page_num,
                    "indexed_date": datetime.now(timezone.utc),
                    "text_length": len(content),
                    "section_number": chunk_dict["section_number"],
                    "section_title": chunk_dict["section_title"],
                    "parent_section": chunk_dict["parent_section"],
                    "chunk_type": chunk_dict["chunk_type"],
                    "vectorContent": embedding,
                }

                filtered_doc = self.prepare_document(base_doc)
                if "id" in filtered_doc:
                    documents.append(filtered_doc)

        return documents

    def process_html_files(self) -> List[Dict[str, Any]]:
        """Process markdown table files — one chunk per table, with section context."""
        documents = []
        html_files = sorted(Path(self.html_dir).glob("*.md"))

        for file_path in html_files:
            match = re.search(r'page_(\d+)', file_path.stem)
            if not match:
                continue

            page_num = int(match.group(1))

            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Split into individual table blocks (heading + table) on blank-line boundaries
            raw_blocks = re.split(r'\n{2,}', md_content.strip())

            # Group consecutive blocks: optional "## heading" followed by a "| table" block
            table_blocks = []  # list of (extracted_heading, table_md)
            pending_heading = ""
            for block in raw_blocks:
                block = block.strip()
                if block.startswith("## "):
                    pending_heading = block[3:].strip()
                elif block.startswith("|"):
                    table_blocks.append((pending_heading, block))
                    pending_heading = ""

            if not table_blocks:
                continue

            # For tables that have no extracted heading, fall back to text-file section mapping
            section_mappings = self._get_table_section_mappings(page_num, len(table_blocks))

            for table_idx, ((extracted_heading, table_md), ctx) in enumerate(
                zip(table_blocks, section_mappings)
            ):
                doc_id = f"html_page_{page_num}_table_{table_idx + 1}"

                # If PDF heading was extracted, parse section number from it (e.g. "11. FAT" → "11")
                if extracted_heading:
                    m = re.match(r'^(\d+(?:\.\d+)?)[.\s]', extracted_heading)
                    sec_number = m.group(1) if m else ctx["section_number"]
                    parent = sec_number.split(".")[0]
                    table_title = extracted_heading
                else:
                    sec_number = ctx["section_number"]
                    parent = ctx["parent_section"]
                    table_title = ctx["section_title"]

                if table_title:
                    content = (
                        f"Section {sec_number}: {table_title}\n\n"
                        f"{table_md}"
                    )
                else:
                    content = table_md

                try:
                    embedding = self.embeddings.embed_query(content)
                except Exception as e:
                    print(f"[WARNING] Failed to generate embedding for {doc_id}: {e}")
                    embedding = None

                base_doc = {
                    "id": doc_id,
                    "content": content,
                    "filename": file_path.name,
                    "page_number": page_num,
                    "indexed_date": datetime.now(timezone.utc),
                    "text_length": len(content),
                    "section_number": sec_number,
                    "section_title": table_title,
                    "parent_section": parent,
                    "chunk_type": "table",
                    "vectorContent": embedding,
                }

                filtered_doc = self.prepare_document(base_doc)
                if "id" in filtered_doc:
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
        print("\n[2/4] Processing text files (chunking by subsection)...")
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
