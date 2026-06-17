import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1

s21=[c for c in chunks if '[S21]' in c['content']][0]
tok=len(enc.encode(s21['content']))
print(f'S21 chunk: {tok} cl100k tokens, stored content length {len(s21["content"])} chars')
print(f'max_tokens registered for bge-m3 = 2048')
print(f'-> RAGFlow truncates to ~2048*0.95 BEFORE embedding; STORED content stays full ({tok} tok).')
print(f'   So: the FULL text is searchable by keyword, but the VECTOR only "sees" the first ~1950 tok.\n')

# What's at the START vs END of S21? If the answer to a question is in the tail,
# vector search may miss it (the tail wasn't embedded).
content=s21['content']
print('S21 HEAD (embedded):', content[:140].replace('\n',' '))
print('S21 TAIL (NOT embedded - beyond ~2048 tok):', content[-140:].replace('\n',' '))

# Demonstrate: can we retrieve S21 by a query about its TAIL content?
tail_words=re.findall(r'[א-ת]{4,}', content[-400:])
print('\nsample words from the TAIL of S21:', tail_words[:8])

# how many chunks exceed the 2048 embed cap (their vectors are truncated)?
over=[c for c in chunks if len(enc.encode(c['content']))>2048]
print(f'\nchunks whose stored content EXCEEDS the 2048 embed cap (vector truncated): {len(over)}/{len(chunks)}')
for c in over:
    t=len(enc.encode(c['content']))
    cap=re.search(r'\[S\d+[^\]]*\]',c['content'][:200])
    print(f'   {t} tok | {cap.group(0) if cap else "?"}')
