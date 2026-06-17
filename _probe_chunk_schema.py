import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

# pull all chunks
chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1

print(f'total chunks: {len(chunks)}\n')
print('=== FULL FIELD SET of one chunk (keys + types) ===')
c0=chunks[0]
for k,v in c0.items():
    val=str(v)
    if len(val)>80: val=val[:80]+'...'
    print(f'  {k:24s} ({type(v).__name__}): {val}')

# Is there a dedicated title/metadata field, or is the title only inside content?
print('\n=== Looking for where the section title lives ===')
import re
sample=chunks[5]
title_in_content = bool(re.search(r'\[S\d+', sample.get('content','')[:120]))
print('keys present:', sorted(c0.keys()))
print('content starts with [S#]?', title_in_content)
print('content head:', sample.get('content','')[:120].replace('\n',' '))
