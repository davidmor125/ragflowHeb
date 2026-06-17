import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
OLD_DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'
DOCX='_client_spec.docx'

# 0. confirm dataset config has parent_child ON (set earlier)
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('dataset config: chunk_token_num=',pc.get('chunk_token_num'),
      'use_parent_child=',pc.get('parent_child',{}).get('use_parent_child'),
      'enable_children=',pc.get('enable_children'))

# 1. delete the old document (its config was stale)
r=requests.delete(f'{BASE}/datasets/{DID}/documents',headers=HJ,json={'ids':[OLD_DOC]},timeout=60).json()
print('delete old doc:',r.get('code'))

# 2. re-upload fresh -> inherits dataset's current parser_config
with open(DOCX,'rb') as fh:
    up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,
        files={'file':('client_spec.docx',fh)},timeout=120).json()
if up.get('code')!=0:
    print('UPLOAD FAIL:',up); sys.exit(1)
NEW_DOC=up['data'][0]['id']
print('new doc id:',NEW_DOC)

# verify the NEW document inherited parent_child
docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={NEW_DOC}',headers=H,timeout=30).json()
ndoc=docs['data']['docs'][0]
npc=ndoc.get('parser_config',{})
print('NEW doc config: chunk_token_num=',npc.get('chunk_token_num'),
      'use_parent_child=',npc.get('parent_child',{}).get('use_parent_child'),
      'children_delimiter=',repr(npc.get('children_delimiter')),
      'enable_children=',npc.get('enable_children'))

# 3. parse
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[NEW_DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'))
t0=time.time(); last=None
while time.time()-t0<2400:
    docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={NEW_DOC}',headers=H,timeout=30).json()
    dd=docs['data']['docs'][0]
    run,prog=str(dd['run']),round(dd.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} prog={prog} chunks={dd.get("chunk_count",0)}')
        last=(run,prog)
    if run in ('3','DONE') and dd.get('progress',0)>=1: break
    if run in ('4','FAIL'):
        print('PARSE FAILED:',(dd.get('progress_msg','') or '')[-400:]); sys.exit(1)
    time.sleep(8)
print(f'DONE chunk_count={dd.get("chunk_count")}')
print('NEW_DOC='+NEW_DOC)
save('reupload_pc_done',{'new_doc':NEW_DOC,'chunk_count':dd.get('chunk_count'),'config':npc})
