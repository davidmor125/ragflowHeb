import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'
OLD_MD_DOC='2997e12665ed11f19d1425719d627201'

# 1. drop the base64-polluted original md doc
r=requests.delete(f'{BASE}/datasets/{DS}/documents',headers=HJ,json={'ids':[OLD_MD_DOC]},timeout=60).json()
print('delete polluted md doc:',r.get('code'))

# 2. testdoc v3: same content, image section replaced by a plain sentence
src=open('_contract_testdoc.md',encoding='utf-8').read()
v3=re.sub(r'!\[תרשים מכירות\]\(data:image/png;base64,[^)]+\)\n*',
          '', src)
v3=v3.replace('התמונה לעיל מציגה נתוני מכירות רבעוניים.',
              'תרשים המכירות הרבעוני מופיע בקובץ ה-PDF הנלווה (testdoc_vision.pdf).')
open('_contract_testdoc_v3.md','w',encoding='utf-8').write(v3)
print('v3 md size:',len(v3.encode('utf-8')),'bytes')

# 3. upload + parse, with timing
t0=time.time()
with open('_contract_testdoc_v3.md','rb') as fh:
    up=requests.post(f'{BASE}/datasets/{DS}/documents',headers=H,
        files={'file':('testdoc.md',fh)},timeout=60).json()
docid=up['data'][0]['id']; t_up=time.time()-t0
save('s4_v3_upload_response',up)
pr=requests.post(f'{BASE}/datasets/{DS}/chunks',headers=HJ,json={'document_ids':[docid]},timeout=30).json()
t0=time.time(); d=None; last=None
while time.time()-t0<900:
    docs=requests.get(f'{BASE}/datasets/{DS}/documents?id={docid}',headers=H,timeout=20).json()
    d=docs['data']['docs'][0]
    run,prog=str(d['run']),round(d.get('progress',0),2)
    if (run,prog)!=last: print(f'  [{int(time.time()-t0):4d}s] run={run} progress={prog}'); last=(run,prog)
    if run in ('3','DONE') and d.get('progress',0)>=1: break
    if run in ('4','FAIL'): print('PARSE FAILED:',d.get('progress_msg','')[-300:]); sys.exit(1)
    time.sleep(5)
t_parse=time.time()-t0
save('s4_v3_doc_final',d)
print(f'v3 md: upload {t_up:.1f}s, parse {t_parse:.0f}s, chunks={d.get("chunk_count")}')

# 4. rerank measurement on clean dataset
RERANK_ID='BAAI/bge-reranker-v2-m3@HuggingFace'
Q='באיזה רבעון נרשם שיא המכירות ומה הערך שלו?'
def retrieval(body,timeout=300):
    t0=time.time()
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=timeout).json()
    return r,time.time()-t0
base={"question":Q,"dataset_ids":[DS],"top_k":1024,"page_size":10,
      "similarity_threshold":0.0,"vector_similarity_weight":0.3}
retrieval(base)  # warm-up
times_no=[];r_no=None
for i in range(3): r_no,dt=retrieval(base); times_no.append(dt)
save('s4_retrieval_no_rerank',r_no)
ch_no=r_no['data']['chunks']
print('NO RERANK times:',[f'{t:.2f}s' for t in times_no],'| chunks:',len(ch_no))
for c in ch_no[:4]: print('   ',round(c["similarity"],3),c['content'][:60].replace('\n',' ').replace('\r',''))

body_rr={**base,"rerank_id":RERANK_ID}
save('s4_retrieval_rerank_request',body_rr)
r1,dt1=retrieval(body_rr,timeout=600)
if r1.get('code')!=0: print('RERANK ERR:',r1.get('message')[:300]); sys.exit(1)
times_rr=[dt1]
for i in range(2): r1,dt=retrieval(body_rr,timeout=600); times_rr.append(dt)
save('s4_retrieval_with_rerank',r1)
ch_rr=r1['data']['chunks']
print(f'WITH RERANK times: first={times_rr[0]:.2f}s then',[f'{t:.2f}s' for t in times_rr[1:]],'| chunks:',len(ch_rr))
for c in ch_rr[:4]: print('   ',round(c["similarity"],3),c['content'][:60].replace('\n',' ').replace('\r',''))

def rank_of_chart(chunks):
    for i,c in enumerate(chunks):
        if '260' in c['content'] and 'Q4' in c['content']: return i
    return -1
print('chart-chunk rank: no-rerank',rank_of_chart(ch_no),'| with-rerank',rank_of_chart(ch_rr))
summary={"question":Q,"rerank_id":RERANK_ID,
 "times_no_rerank_s":[round(t,2) for t in times_no],
 "times_with_rerank_s":[round(t,2) for t in times_rr],
 "rank_chart_no":rank_of_chart(ch_no),"rank_chart_rr":rank_of_chart(ch_rr),
 "md_v3_doc_id":docid,"md_v3_parse_s":round(t_parse,1)}
save('s4_rerank_summary',summary)
print('V3_DOC_ID='+docid)
