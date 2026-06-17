import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
docid={d['name']:d['id'] for d in docs}['20071.html']
PHRASE='אינה חייבת בדיווח'

# STEP 1: find ALL chunks in 20071 that contain the phrase, show their full text
all_chunks=[];page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{docid}/chunks?page={page}&page_size=200',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    all_chunks.extend(cs); page+=1
print(f'20071 has {len(all_chunks)} chunks total')
answer_chunks=[c for c in all_chunks if PHRASE in c['content']]
print(f'chunks containing "{PHRASE}": {len(answer_chunks)}')
for c in answer_chunks:
    print(f'\n  --- answer chunk id={c["id"]} ---')
    print('  '+c['content'][:300].replace('\n',' '))

# STEP 2: retrieve top-30 (restricted to 20071) and find WHERE this exact chunk ranks
q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'document_ids':[docid],'page_size':30,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
    'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=120).json()
retrieved=r['data']['chunks']
answer_ids={c['id'] for c in answer_chunks}
print(f'\n=== Where does the answer chunk rank in top-30 (restricted to 20071, with rerank)? ===')
found=False
for i,c in enumerate(retrieved):
    if c['id'] in answer_ids or PHRASE in c.get('content',''):
        print(f'  >>> ANSWER CHUNK is at RANK {i+1}, sim={c.get("similarity",0):.3f}')
        found=True
if not found:
    print(f'  *** answer chunk NOT in top-30 at all! Total retrieved: {len(retrieved)} ***')
    print(f'  (total candidates considered: {r["data"].get("total")})')
