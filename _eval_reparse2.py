import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

# read current dataset config
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
cur=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
print('current dataset chunk_method:',cur.get('chunk_method'))
print('current parser_config:',json.dumps(cur.get('parser_config',{}),ensure_ascii=False)[:300])

# update dataset-level parser_config: small chunks, graphrag OFF, no enrichment
new_cfg={"chunk_token_num":128,"delimiter":"\n","layout_recognize":"DeepDOC",
         "auto_keywords":0,"auto_questions":0,
         "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False}}
r=requests.put(f'{BASE}/datasets/{DID}',headers=HJ,
    json={"chunk_method":"naive","parser_config":new_cfg},timeout=30).json()
print('PUT dataset config:',r.get('code'),r.get('message',''))

# verify it took
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
cur=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
print('after update parser_config:',json.dumps(cur.get('parser_config',{}),ensure_ascii=False)[:300])

# re-parse
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'),pr.get('message',''))
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
        save('eval_reparse2_FAIL',d); sys.exit(1)
    time.sleep(8)
save('eval_reparse2_done',d)
print(f'DONE chunks={d.get("chunk_count")} parser_config_used={json.dumps(d.get("parser_config",{}),ensure_ascii=False)[:200]}')
