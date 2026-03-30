"""
Test FACTORY ACCEPTANCE TESTING query with detailed timing
"""
import sys
import time
sys.path.insert(0, 'src')
import requests

print('Testing FACTORY ACCEPTANCE TESTING (FAT) table query...')
print('=' * 80)

# Increase client timeout significantly
start = time.time()

try:
    print('[1/3] Sending request to API...')
    response = requests.post(
        'http://localhost:3001/api/llm-response',
        json={
            'query': 'FACTORY ACCEPTANCE TESTING (FAT) table',
            'top_docs': 5
        },
        timeout=120  # 2 minute timeout
    )
    elapsed = time.time() - start
    
    print(f'[2/3] Response received in {elapsed:.2f} seconds')
    print(f'[3/3] Status: {response.status_code}')
    
    if response.status_code == 200:
        result = response.json()
        print(f'\nSUCCESS!')
        print(f'Documents used: {result["documents_used"]}')
        print(f'Response length: {len(result["llm_response"])} chars')
        print(f'\nFirst 400 chars:')
        print(result['llm_response'][:400])
    else:
        print(f'ERROR: {response.status_code}')
        print(response.text[:500])
except requests.exceptions.Timeout:
    print(f'REQUEST TIMEOUT after 120 seconds!')
except requests.exceptions.ConnectionError as e:
    print(f'CONNECTION ERROR: {e}')
except Exception as e:
    print(f'ERROR: {str(e)}')
