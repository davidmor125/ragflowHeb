import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DOCX='_client_spec.docx'

# 1. create a fresh dataset with Qwen3 embedding + winning chunk config
cfg={"chunk_token_num":256,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False},
     "parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
ds_body={"name":f"qwen3_spec_{int(time.time())}","embedding_model":"qwen3-embedding:4b@Ollama",
         "chunk_method":"naive","parser_config":cfg}
r=requests.post(f'{BASE}/datasets',headers=HJ,json=ds_body,timeout=30).json()
if r.get('code')!=0:
    print('CREATE FAIL:',r); sys.exit(1)
DID=r['data']['id']
print('dataset:',DID,'| embedding:',r['data'].get('embedding_model'))
save('qwen3_dataset',r['data'])

# 2. upload + parse
with open(DOCX,'rb') as fh:
    up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,
        files={'file':('client_spec.docx',fh)},timeout=120).json()
if up.get('code')!=0:
    print('UPLOAD FAIL:',up); sys.exit(1)
DOC=up['data'][0]['id']
print('doc:',DOC)
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'))
t0=time.time(); last=None
while time.time()-t0<2400:
    docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={DOC}',headers=H,timeout=30).json()
    dd=docs['data']['docs'][0]
    run,prog=str(dd['run']),round(dd.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} prog={prog} chunks={dd.get("chunk_count",0)}')
        last=(run,prog)
    if run in ('3','DONE') and dd.get('progress',0)>=1: break
    if run in ('4','FAIL'):
        print('PARSE FAILED:',(dd.get('progress_msg','') or '')[-500:]); sys.exit(1)
    time.sleep(8)
print(f'DONE chunk_count={dd.get("chunk_count")}')
print('QWEN_DID='+DID)
print('QWEN_DOC='+DOC)
save('qwen3_parse_done',{'did':DID,'doc':DOC,'chunks':dd.get('chunk_count')})
