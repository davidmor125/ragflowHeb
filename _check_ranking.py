import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'

# Q4: restricted to procedure 20071, look at FULL ranking with scores
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
docid={d['name']:d['id'] for d in docs}['20071.html']

q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
phrase='אינה חייבת בדיווח'   # the correct-answer phrase

print('=== WITH Qwen reranker (restricted to 20071), top 15 ranked ===')
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'document_ids':[docid],'page_size':15,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
    'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=120).json()
for i,c in enumerate(r['data']['chunks']):
    has = '<<< HAS ANSWER' if phrase in c.get('content','') else ''
    print(f'  rank{i+1:2d} sim={c.get("similarity",0):.3f} {has} | {c["content"][:55].replace(chr(10)," ")}')

print('\n=== WITHOUT reranker (pure vector+keyword), top 15 ===')
r2=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'document_ids':[docid],'page_size':15,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
for i,c in enumerate(r2['data']['chunks']):
    has = '<<< HAS ANSWER' if phrase in c.get('content','') else ''
    print(f'  rank{i+1:2d} sim={c.get("similarity",0):.3f} {has} | {c["content"][:55].replace(chr(10)," ")}')
