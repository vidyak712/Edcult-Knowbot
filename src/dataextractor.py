import os
import fitz  # PyMuPDF

def is_valid_table(table) -> bool:
    """Filter out false positives (headers, footers) — require >=3 rows, >=2 cols, >=3 filled cells."""
    if table.row_count < 3 or table.col_count < 2:
        return False
    rows = table.extract()
    non_empty = sum(1 for row in rows for cell in row if cell and str(cell).strip())
    return non_empty >= 3

def extract_tables_as_html(page) -> list:
    """Extract all valid tables from a page and return as HTML strings."""
    html_tables = []
    try:
        tabs = page.find_tables()
        if tabs.tables:
            for idx, table in enumerate(tabs.tables):
                if is_valid_table(table):
                    rows = table.extract()
                    html = _table_to_html(rows)
                    html_tables.append(html)
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
    text_dir   = os.path.join(output_dir, "text")
    html_dir   = os.path.join(output_dir, "html")
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
            # Extract text and tables as Markdown
            text = page.get_text()
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
                    for table_md in html_tables:
                        f.write(table_md)
                        f.write("\n\n")
                page_info["html_file"] = md_path  # Keep key name for compatibility
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
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path   = os.path.join(project_root, "input", "Compressor_Specification.pdf")
    output_dir = os.path.join(project_root, "output", "extracted_content")

    result = extract_content(pdf_path, output_dir)

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