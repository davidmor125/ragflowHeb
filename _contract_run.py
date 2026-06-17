import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'; os.makedirs(OUT,exist_ok=True)
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

# ---- use the dataset created in section 1 (re-create fresh to be self-contained) ----
ds_body={"name":"contract_accept_"+str(int(time.time())),"embedding_model":"bge-m3@Ollama","chunk_method":"naive",
  "parser_config":{"chunk_token_num":512,"layout_recognize":"DeepDOC","auto_keywords":3,"auto_questions":2,
  "raptor":{"use_raptor":False}}}  # raptor off for speed on acceptance run
ds=requests.post(f'{BASE}/datasets',headers=HJ,json=ds_body,timeout=30).json()
did=ds['data']['id']; print('dataset:',did)

# ---- S2: upload (md) ----
t0=time.time()
with open('_contract_testdoc.md','rb') as fh:
    up=requests.post(f'{BASE}/datasets/{did}/documents',headers=H,files={'file':('testdoc.md',fh)},timeout=60).json()
docid=up['data'][0]['id']; t_up=time.time()-t0
save('s2_upload_response',up)
print(f'S2 upload code={up["code"]} doc_id={docid} ({t_up:.1f}s)')

# ---- S2: parse trigger ----
pr=requests.post(f'{BASE}/datasets/{did}/chunks',headers=HJ,json={'document_ids':[docid]},timeout=30).json()
print('S2 parse trigger code=',pr.get('code'))
t_parse0=time.time()

# ---- S2: poll until run=3 ----
last=None
while time.time()-t_parse0 < 1200:
    docs=requests.get(f'{BASE}/datasets/{did}/documents',headers=H,timeout=20).json()
    d=docs['data']['docs'][0]
    run,prog,cc=str(d['run']),round(d.get('progress',0),2),d.get('chunk_count',0)
    if (run,prog)!=last:
        print(f'   [{int(time.time()-t_parse0):4d}s] run={run} progress={prog} chunks={cc}')
        last=(run,prog)
    if run=='3': t_parse=time.time()-t_parse0; print(f'S2 PARSE DONE in {t_parse:.0f}s, chunks={cc}'); break
    if run=='4': print('S2 PARSE FAILED:',d.get('progress_msg','')[-300:]); save('s2_doc_final',d); sys.exit(1)
    time.sleep(6)
save('s2_doc_final',d)

# ---- inspect chunks: did inline anchor survive? did image get described? ----
import urllib.parse
ch=requests.get(f'{BASE}/datasets/{did}/documents/{docid}/chunks?page=1&page_size=200',headers=H,timeout=30).json()
save('s2_chunks',ch)
chunks=ch['data']['chunks'] if 'chunks' in ch.get('data',{}) else ch['data'].get('chunk_list',[])
allc=' '.join(c.get('content','')+c.get('content_with_weight','') for c in chunks)
print(f'   total chunks: {len(chunks)}')
print(f'   inline anchor survived: {"מסמך-בדיקה-12345" in allc}')
print(f'   table secret ZX9871 present: {"ZX9871" in allc}')
print(f'   mermaid key MERMAIDKEY42 present: {"MERMAIDKEY42" in allc}')
print(f'   image VISION (Q4/260/sales) present: {any(k in allc for k in ["260","Q4","מכירות","sales","SALES"])}')

print('DATASET_ID='+did)
print('DOC_ID='+docid)
