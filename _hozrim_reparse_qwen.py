import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='dc0091ca46e211f196f633ac796a3d7a'

# 1. set config: Qwen embedding + parent_child + chunk 256, NO graphrag, NO raptor, NO enrichment
cfg={"chunk_token_num":256,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False},
     "parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
r=requests.put(f'{BASE}/datasets/{DID}',headers=HJ,
    json={"embedding_model":"qwen3-embedding:4b@Ollama","chunk_method":"naive","parser_config":cfg},timeout=60).json()
print('PUT config:',r.get('code'),r.get('message',''))
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('now: embedding=',d.get('embedding_model'),'chunk=',pc.get('chunk_token_num'),
      'parent_child=',pc.get('parent_child',{}).get('use_parent_child'),
      'graphrag=',pc.get('graphrag',{}).get('use_graphrag'),'raptor=',pc.get('raptor',{}).get('use_raptor'))

# 2. list all docs
docs=[]; page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    batch=rr['data']['docs']
    if not batch: break
    docs.extend(batch); page+=1
doc_ids=[x['id'] for x in docs]
print(f'total docs to re-parse: {len(doc_ids)}')

# 3. trigger parse for ALL (RAGFlow queues them; executors process N at a time)
t0=time.time()
B=50
for i in range(0,len(doc_ids),B):
    pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':doc_ids[i:i+B]},timeout=60).json()
    print(f'  triggered batch {i//B+1}: docs {i}-{i+B}, code={pr.get("code")}')
print(f'all parse triggers sent in {time.time()-t0:.0f}s. Now polling until all DONE...')

# 4. poll until all done
last_done=-1
while time.time()-t0 < 6*3600:
    docs=[]; page=1
    while True:
        rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
        batch=rr['data']['docs']
        if not batch: break
        docs.extend(batch); page+=1
    states={}
    for x in docs:
        s=str(x['run']); states[s]=states.get(s,0)+1
    done=states.get('3',0)+states.get('DONE',0)
    fail=states.get('4',0)+states.get('FAIL',0)
    running=states.get('2',0)+states.get('RUNNING',0)+states.get('1',0)
    if done!=last_done:
        el=int(time.time()-t0)
        print(f'  [{el//60}m{el%60}s] DONE={done}/{len(docs)} FAIL={fail} running/pending={running} | states={states}')
        last_done=done
    if done+fail >= len(docs):
        print(f'ALL FINISHED: {done} done, {fail} failed')
        break
    time.sleep(30)

ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
print(f'final chunk_count={d.get("chunk_count")}')
save('hozrim_qwen_reparse',{'embedding':d.get('embedding_model'),'chunks':d.get('chunk_count'),'docs':len(doc_ids)})
print('REPARSE COMPLETE')
