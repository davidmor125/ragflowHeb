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
q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'document_ids':[docid],'page_size':3,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
    'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=120).json()
c=r['data']['chunks'][0]
print('=== FULL content of the rank-1 chunk (the one with the answer) ===')
print(c['content'])
print('\n=== length:',len(c['content']),'chars ===')
