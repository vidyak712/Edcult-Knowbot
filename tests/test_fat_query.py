"""
Test FACTORY ACCEPTANCE TESTING query for timeouts/issues
"""
import sys
import time
sys.path.insert(0, 'src')
import requests

print('Testing FACTORY ACCEPTANCE TESTING query...')
print('=' * 80)
start = time.time()

try:
    response = requests.post(
        'http://localhost:3001/api/llm-response',
        json={
            'query': 'FACTORY ACCEPTANCE TESTING (FAT) table',
            'top_docs': 5
        },
        timeout=30
    )
    elapsed = time.time() - start
    
    print(f'Response received in {elapsed:.2f} seconds')
    print(f'Status: {response.status_code}')
    
    if response.status_code == 200:
        result = response.json()
        print(f'Documents used: {result["documents_used"]}')
        print(f'Response length: {len(result["llm_response"])} chars')
        print('First 300 chars of response:')
        print(result['llm_response'][:300])
    else:
        print('Error:', response.text[:500])
except requests.exceptions.Timeout:
    print('REQUEST TIMEOUT after 30 seconds!')
except Exception as e:
    print(f'Error: {str(e)}')
