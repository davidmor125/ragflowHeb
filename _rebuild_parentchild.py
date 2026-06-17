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

# 1. enable built-in parent/child + smaller chunk size (the system's own settings)
cfg={"chunk_token_num":256,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False},
     "parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
r=requests.put(f'{BASE}/datasets/{DID}',headers=HJ,
    json={"chunk_method":"naive","parser_config":cfg},timeout=30).json()
print('PUT config:',r.get('code'),r.get('message',''))

# verify it persisted
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('persisted: chunk_token_num=',pc.get('chunk_token_num'),
      'enable_children=',pc.get('enable_children'),
      'parent_child=',pc.get('parent_child'),
      'children_delimiter=',repr(pc.get('children_delimiter')))
save('rebuild_pc_config',pc)

# 2. re-parse
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'))
t0=time.time(); last=None; doc=None
while time.time()-t0<2400:
    docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={DOC}',headers=H,timeout=30).json()
    doc=docs['data']['docs'][0]
    run,prog=str(doc['run']),round(doc.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} prog={prog} chunks={doc.get("chunk_count",0)}')
        last=(run,prog)
    if run in ('3','DONE') and doc.get('progress',0)>=1: break
    if run in ('4','FAIL'):
        print('PARSE FAILED:',(doc.get('progress_msg','') or '')[-500:])
        save('rebuild_pc_FAIL',doc); sys.exit(1)
    time.sleep(8)
save('rebuild_pc_done',doc)
print(f'DONE: server={doc.get("process_duration")}s chunk_count={doc.get("chunk_count")}')
print('msg tail:',(doc.get('progress_msg','') or '')[-300:])
