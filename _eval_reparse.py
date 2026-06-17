import sys, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
enc=tiktoken.get_encoding('cl100k_base')
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'
DOCX='_client_spec.docx'

# 1. Update the document's parser_config to smaller chunks + no graphrag + no enrichment
# (graphrag/enrichment were on by default and add long LLM-call load; keep retrieval-only for eval)
cfg={"chunk_token_num":256,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False}}
r=requests.put(f'{BASE}/datasets/{DID}/documents/{DOC}',headers=HJ,
    json={"parser_config":cfg},timeout=30).json()
print('update parser_config:',r.get('code'),r.get('message',''))

# 2. (re)trigger parse
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'),pr.get('message',''))

# 3. poll
t0=time.time(); last=None; d=None
while time.time()-t0<2400:
    docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={DOC}',headers=H,timeout=30).json()
    d=docs['data']['docs'][0]
    run,prog=str(d['run']),round(d.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} progress={prog} chunks={d.get("chunk_count",0)}')
        last=(run,prog)
    if run in ('3','DONE') and d.get('progress',0)>=1: break
    if run in ('4','FAIL'):
        print('PARSE FAILED:',(d.get('progress_msg','') or '')[-500:])
        save('eval_reparse_FAIL',d); sys.exit(1)
    time.sleep(8)
save('eval_reparse_done',d)
print(f'DONE: server={d.get("process_duration")}s chunks={d.get("chunk_count")}')
print('msg tail:',(d.get('progress_msg','') or '')[-300:])
