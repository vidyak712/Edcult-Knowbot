import io
import os
import tempfile

import fitz  # PyMuPDF
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

def is_valid_table(table) -> bool:
    """Filter out false positives (headers, footers) — require >=3 rows, >=2 cols, >=3 filled cells."""
    if table.row_count < 3 or table.col_count < 2:
        return False
    rows = table.extract()
    non_empty = sum(1 for row in rows for cell in row if cell and str(cell).strip())
    return non_empty >= 3

def get_table_heading(page, table_bbox) -> str:
    """Find the nearest text line directly above the table bounding box on the page.

    Returns the heading string, or empty string if none found within a reasonable distance.
    """
    # table_bbox is a tuple (x0, y0, x1, y1)
    table_top = table_bbox[1]
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

    best_text = ""
    best_dist = float("inf")

    for block in blocks:
        bx0, by0, bx1, by1, btext, *_ = block
        btext = btext.strip()
        if not btext or len(btext) < 3:
            continue
        # Block must be above the table top
        if by1 > table_top:
            continue
        dist = table_top - by1
        # Only consider blocks within 80 points (~28mm) above the table
        if dist < best_dist and dist <= 80:
            best_dist = dist
            best_text = btext.replace("\n", " ").strip()

    return best_text

def extract_tables_as_html(page) -> list:
    """Extract all valid tables from a page and return as (heading, markdown) tuples."""
    html_tables = []
    try:
        tabs = page.find_tables()
        if tabs.tables:
            for table in tabs.tables:
                if is_valid_table(table):
                    rows = table.extract()
                    md = _table_to_html(rows)
                    heading = get_table_heading(page, table.bbox)
                    html_tables.append((heading, md))
    except Exception:
        pass
    return html_tables

def _table_to_html(rows: list) -> str:
    """Convert table rows to Markdown table format."""
    if not rows:
        return ""
    
    # Create markdown table
    markdown = ""
    for row_idx, row in enumerate(rows):
        cells = [str(cell).strip() if cell else "" for cell in row]
        markdown += "| " + " | ".join(cells) + " |\n"
        
        # Add separator after header row (first row)
        if row_idx == 0:
            markdown += "|" + "|".join(["---"] * len(cells)) + "|\n"
    
    return markdown

def extract_prose_text(page) -> str:
    """Extract text from a page, skipping blocks that fall inside table regions."""
    table_bboxes = []
    try:
        tabs = page.find_tables()
        if tabs.tables:
            for table in tabs.tables:
                if is_valid_table(table):
                    table_bboxes.append(table.bbox)  # (x0, y0, x1, y1)
    except Exception:
        pass

    if not table_bboxes:
        return page.get_text()

    prose_parts = []
    for block in page.get_text("blocks"):  # (x0, y0, x1, y1, text, block_no, block_type)
        bx0, by0, bx1, by1, btext, *_ = block
        btext = btext.strip()
        if not btext:
            continue
        in_table = False
        for tx0, ty0, tx1, ty1 in table_bboxes:
            overlap_x = max(0.0, min(bx1, tx1) - max(bx0, tx0))
            overlap_y = max(0.0, min(by1, ty1) - max(by0, ty0))
            block_area = max(1.0, (bx1 - bx0) * (by1 - by0))
            if (overlap_x * overlap_y) / block_area > 0.5:
                in_table = True
                break
        if not in_table:
            prose_parts.append(btext)

    return "\n".join(prose_parts)


def detect_tables_on_page(page) -> bool:
    """Detect tables using PyMuPDF's page.find_tables(). Returns True if any valid table is found."""
    try:
        tabs = page.find_tables()
        return bool(tabs.tables) and any(is_valid_table(t) for t in tabs.tables)
    except Exception:
        return False

def extract_content(pdf_path: str, output_dir: str) -> dict:
    """
    Smart extraction from PDF:
    - Pages with tables                → text + HTML tables to /text and /html, structured data to /json and /csv
    - Text-only pages                  → text saved as TXT to /text
    """
    text_dir   = os.path.join(output_dir, "text-1")
    html_dir   = os.path.join(output_dir, "html-1")
    os.makedirs(text_dir, exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    pages_data = {}
    total_table_pages = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_key = f"page_{page_num + 1}"

        has_tables = detect_tables_on_page(page)

        if has_tables:
            total_table_pages += 1

        page_info = {
            "has_tables": has_tables,
            "extraction_type": None,
        }

        if has_tables:
            # Extract prose only (table rows are stored separately in the .md file)
            text = extract_prose_text(page)
            text_path = os.path.join(text_dir, f"{page_key}_text.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)
            page_info["text_file"] = text_path
            page_info["text_length"] = len(text)
            
            # Extract tables as Markdown
            html_tables = extract_tables_as_html(page)
            if html_tables:
                md_path = os.path.join(html_dir, f"{page_key}_tables.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    for heading, table_md in html_tables:
                        if heading:
                            f.write(f"## {heading}\n\n")
                        f.write(table_md)
                        f.write("\n\n")
                page_info["html_file"] = md_path
                page_info["table_count"] = len(html_tables)
            
            page_info["extraction_type"] = "table"
        else:
            # Extract plain text
            text = page.get_text()
            text_path = os.path.join(text_dir, f"{page_key}_text.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)
            page_info["text_length"] = len(text)
            page_info["text_file"] = text_path
            page_info["extraction_type"] = "text"

        pages_data[page_key] = page_info

    doc.close()

    return {
        "total_pages": len(pages_data),
        "total_table_pages": total_table_pages,
        "pages": pages_data,
    }

def main():
    load_dotenv()

    blob_endpoint  = os.environ["AZURE_BLOB_STORAGE_END_POINT"].strip()
    blob_key       = os.environ["AZURE_BLOB_STORAGE_KEY"].strip()
    container_name = os.environ["AZURE_BLOB_STORAGE_RESOURCE_CONTAINER"].strip()
    blob_name      = "k2001_compressor_manual.pdf"

    blob_service = BlobServiceClient(
        account_url=blob_endpoint,
        credential=blob_key,
    )
    blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)

    pdf_bytes = blob_client.download_blob().readall()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "output", "extracted_content")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = extract_content(tmp_path, output_dir)
    finally:
        os.unlink(tmp_path)

    text_pages  = sum(1 for p in result["pages"].values() if p["extraction_type"] == "text")
    table_pages = sum(1 for p in result["pages"].values() if p["extraction_type"] == "table")

    print(f"\n✓ Extraction complete!")
    print(f"  Total pages: {result['total_pages']}")
    print(f"  Text-only pages: {text_pages}")
    print(f"  Pages with tables: {table_pages}\n")

    print("Page details:")
    for page_key, info in result["pages"].items():
        ext = info["extraction_type"].upper()
        if ext == "TEXT":
            print(f"  {page_key}: [TEXT] {info['text_length']:,} chars")
        elif ext == "TABLE":
            tables = info.get("table_count", 0)
            print(f"  {page_key}: [TABLE] {tables} table(s) extracted as HTML, {info.get('text_length', 0):,} chars text")

if __name__ == "__main__":
    main()
