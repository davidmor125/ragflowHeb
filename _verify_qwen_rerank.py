import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='0438ba6466fa11f1a56021ba47a3a9e1'   # Qwen3-embedding dataset

q='מהם השלבים האפשריים של סטטוס הזמנה?'
def retr(rerank_id=None):
    body={'question':q,'dataset_ids':[DID],'page_size':6,'similarity_threshold':0.0,
          'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']}
    if rerank_id: body['rerank_id']=rerank_id
    t0=time.time()
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()
    return r,time.time()-t0

# without rerank
r0,t0=retr()
if r0.get('code')!=0: print('no-rerank ERR:',r0); sys.exit(1)
print(f'NO RERANK ({t0:.1f}s): top sims =',[round(c["similarity"],3) for c in r0['data']['chunks'][:5]])

# with Qwen reranker (the native rerank_id)
r1,t1=retr('Qwen3-Reranker-4B@HuggingFace')
if r1.get('code')!=0:
    print('QWEN RERANK ERR:',r1.get('message')[:300]); sys.exit(1)
print(f'QWEN RERANK ({t1:.1f}s): top sims =',[round(c["similarity"],3) for c in r1['data']['chunks'][:5]])
print('\nQwen reranker is WIRED and working through RAGFlow native path.')
print('top-1 after Qwen rerank:', r1['data']['chunks'][0]['content'][:70].replace(chr(10),' '))
