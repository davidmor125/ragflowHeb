import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='c8482642674011f1a56221ba47a3a9e1'

# find 78634 doc, look at chunks containing "חשמונאים" or "רב מותגי"
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
docid={d['name']:d['id'] for d in docs}['78634.html']

chunks=[];page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{docid}/chunks?page={page}&page_size=200',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1
print(f'78634 has {len(chunks)} chunks')
# search for the branch table content
for kw in ['חשמונאים','רב מותגי','מוביל','אוצה','361']:
    hits=[i for i,c in enumerate(chunks) if kw in c['content']]
    print(f'  "{kw}" appears in chunks: {hits[:8]}')
# show chunks that mention רב מותגי / מוביל
print('\nchunks mentioning the branch structure:')
for i,c in enumerate(chunks):
    if 'רב מותגי' in c['content'] or 'מוביל' in c['content'] or 'חשמונאים' in c['content']:
        print(f'  chunk{i}: {c["content"][:200].replace(chr(10)," ")}')
        print()
