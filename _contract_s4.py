import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'
RERANK_ID='BAAI/bge-reranker-v2-m3@HuggingFace'
Q='באיזה רבעון נרשם שיא המכירות ומה הערך שלו?'

def retrieval(body):
    t0=time.time()
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()
    return r, time.time()-t0

base_body={"question":Q,"dataset_ids":[DS],"top_k":1024,"page_size":10,
           "similarity_threshold":0.0,"vector_similarity_weight":0.7}

# warm-up (ES + embedding model load) — not measured
retrieval(base_body)

# ---- without rerank: 3 runs ----
times_no=[]; r_no=None
for i in range(3):
    r_no,dt=retrieval(base_body); times_no.append(dt)
save('s4_retrieval_no_rerank',r_no)
ch_no=r_no['data']['chunks']
print('NO RERANK  times:',[f'{t:.2f}s' for t in times_no])
print('  top-3:',[(c['content'][:40].replace(chr(10),' '),round(c['similarity'],3)) for c in ch_no[:3]])

# ---- with rerank: 3 runs ----
body_rr={**base_body,"rerank_id":RERANK_ID}
save('s4_retrieval_rerank_request',body_rr)
r_rr,dt0=retrieval(body_rr)
times_rr=[dt0]
for i in range(2):
    r_rr,dt=retrieval(body_rr); times_rr.append(dt)
save('s4_retrieval_with_rerank',r_rr)
if r_rr.get('code')!=0:
    print('RERANK FAILED:',r_rr.get('message')); sys.exit(1)
ch_rr=r_rr['data']['chunks']
print(f'WITH RERANK times: first(load)={times_rr[0]:.2f}s then',[f'{t:.2f}s' for t in times_rr[1:]])
print('  top-3:',[(c['content'][:40].replace(chr(10),' '),round(c['similarity'],3)) for c in ch_rr[:3]])

# correctness: is the VISION chart chunk (260/Q4) ranked first?
def rank_of_chart(chunks):
    for i,c in enumerate(chunks):
        if '260' in c['content'] and 'Q4' in c['content']: return i
    return -1
print('chart-chunk rank no-rerank:',rank_of_chart(ch_no),' with-rerank:',rank_of_chart(ch_rr))

summary={"question":Q,"rerank_id":RERANK_ID,
  "times_no_rerank_s":[round(t,2) for t in times_no],
  "times_with_rerank_s":[round(t,2) for t in times_rr],
  "rank_of_chart_chunk_no_rerank":rank_of_chart(ch_no),
  "rank_of_chart_chunk_with_rerank":rank_of_chart(ch_rr),
  "top3_no":[c['content'][:60] for c in ch_no[:3]],
  "top3_rr":[c['content'][:60] for c in ch_rr[:3]]}
save('s4_rerank_summary',summary)
print('SECTION 4 DONE')
