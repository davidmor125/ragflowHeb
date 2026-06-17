import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'

# Take Q4 (procedure 20071, has a clear expected answer)
q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
proc='20071'

print('=== 1. CHUNK STRUCTURE: what does a retrieved chunk actually contain? ===')
def retr(rerank=None):
    body={'question':q,'dataset_ids':[DID],'page_size':6,'similarity_threshold':0.0,
          'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']}
    if rerank: body['rerank_id']=rerank
    return requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()

r=retr('Qwen3-Reranker-4B@HuggingFace')
ch=r['data']['chunks']
print(f'retrieved {len(ch)} chunks. Full field inspection of top chunk:')
c0=ch[0]
for k,v in c0.items():
    val=str(v)
    print(f'  {k}: {val[:80]}')

print('\n=== 2. Are these chunks even from procedure 20071? (check content) ===')
for i,c in enumerate(ch):
    cont=c.get('content','')
    has20071 = '20071' in cont or 'תמנון' in cont or 'בלתי רגיל' in cont
    print(f'  chunk{i} sim={c.get("similarity",0):.3f} relevant_keywords={has20071} | {cont[:60].replace(chr(10)," ")}')

print('\n=== 3. WITH vs WITHOUT reranker: does Qwen reranker help or hurt? ===')
r_no=retr()
r_rr=retr('Qwen3-Reranker-4B@HuggingFace')
print('top-3 WITHOUT rerank:')
for c in r_no['data']['chunks'][:3]:
    print(f'  sim={c.get("similarity",0):.3f} | {c.get("content","")[:55].replace(chr(10)," ")}')
print('top-3 WITH Qwen rerank:')
for c in r_rr['data']['chunks'][:3]:
    print(f'  sim={c.get("similarity",0):.3f} | {c.get("content","")[:55].replace(chr(10)," ")}')

print('\n=== 4. Does the ANSWER actually exist in any retrieved chunk? ===')
# expected answer mentions "אינה חייבת בדיווח" / branch check
allc=' '.join(c.get('content','') for c in r_rr['data']['chunks'])
for kw in ['אינה חייבת בדיווח','בדיקת הסניף','תיאור המקרה','תקין']:
    print(f'  "{kw}" in retrieved chunks: {kw in allc}')
