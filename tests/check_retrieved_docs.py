"""
Check documents retrieved for APPLICABLE CODES AND STANDARDS query
"""
import sys
sys.path.insert(0, 'src')
from azure_llm_handler import search_azure_index

results = search_azure_index('APPLICABLE CODES AND STANDARDS', top=10)
docs = results.get('value', [])

print('DOCUMENTS RETRIEVED FOR: APPLICABLE CODES AND STANDARDS')
print('=' * 80)
print(f'Total documents found: {len(docs)}\n')

for i, doc in enumerate(docs, 1):
    filename = doc.get('filename', 'Unknown')
    doc_id = doc.get('id', 'N/A')
    page_num = doc.get('page_number', 'N/A')
    text_length = doc.get('text_length', 0)
    content = doc.get('content', '')
    is_html = '<html>' in content.lower() or '<table>' in content.lower()
    
    content_preview = content[:100].replace('\n', ' ')
    doc_type = 'HTML Table' if is_html else 'Text'
    
    print(f'[{i}] {filename}')
    print(f'    ID: {doc_id}')
    print(f'    Page: {page_num}')
    print(f'    Type: {doc_type}')
    print(f'    Length: {text_length} chars')
    print(f'    Content: {content_preview}...')
    print()
