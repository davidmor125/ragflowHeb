import sys, json, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'
IDX='ragflow_2507563a42bd11f1a6bba9e87ac7a32c'

# 1. does doc 20071.html exist in the dataset?
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
names={d['name']:d for d in docs}
for proc in ['20071','20064','12917','78634']:
    f=f'{proc}.html'
    if f in names:
        print(f'{f}: EXISTS, chunks={names[f].get("chunk_count")}, run={names[f]["run"]}')
    else:
        print(f'{f}: *** NOT IN DATASET ***')

# 2. for 20071 — does its content contain the expected answer phrase?
doc20071=names.get('20071.html')
if doc20071:
    did=doc20071['id']
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{did}/chunks?page=1&page_size=200',headers=H,timeout=60).json()
    chunks=ch['data']['chunks']
    allc='\n'.join(c['content'] for c in chunks)
    print(f'\n20071.html has {len(chunks)} chunks, {len(allc)} chars')
    for kw in ['אינה חייבת בדיווח','בדיקת הסניף','תיאור המקרה','תקין','פעולה בלתי רגיל']:
        print(f'  "{kw}" in 20071 content: {kw in allc}')

# 3. THE KEY TEST: if I restrict retrieval to ONLY doc 20071, is the answer there?
    print('\n=== retrieval RESTRICTED to doc 20071 only ===')
    q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
        'document_ids':[did],'page_size':5,'similarity_threshold':0.0,
        'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
    for c in r['data']['chunks'][:5]:
        print(f'  sim={c.get("similarity",0):.3f} | {c["content"][:75].replace(chr(10)," ")}')
