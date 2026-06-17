import sys, json, time, os
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
SRC='dc0091ca46e211f196f633ac796a3d7a'   # hozrim (bge-m3)

# 1. create NEW dataset with Qwen + parent_child + chunk 256, NO graphrag/raptor
cfg={"chunk_token_num":256,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False},
     "parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json={
    "name":f"hozrim_qwen_{int(time.time())}","embedding_model":"qwen3-embedding:4b@Ollama",
    "chunk_method":"naive","parser_config":cfg},timeout=30).json()
assert ds.get('code')==0, ds
DID=ds['data']['id']
print('NEW Qwen dataset:',DID)
save('hozrim_qwen_newds',ds['data'])

# 2. list all source docs
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{SRC}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
print(f'source docs: {len(docs)}')

# 3. download each + upload to new dataset
os.makedirs('_hozrim_files',exist_ok=True)
uploaded=[]
for i,d in enumerate(docs,1):
    did=d['id']; name=os.path.basename(d['name'])
    try:
        r=requests.get(f'{BASE}/datasets/{SRC}/documents/{did}',headers=H,timeout=120)
        if r.status_code!=200 or not r.content:
            print(f'  [{i}] download FAIL {name}: {r.status_code}'); continue
        up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,
            files={'file':(name,r.content)},timeout=120).json()
        if up.get('code')==0:
            uploaded.append(up['data'][0]['id'])
        else:
            print(f'  [{i}] upload FAIL {name}: {up.get("message")}')
    except Exception as e:
        print(f'  [{i}] ERR {name}: {e}')
    if i%50==0: print(f'  copied {i}/{len(docs)} ...')
print(f'uploaded {len(uploaded)} docs to new dataset')
save('hozrim_qwen_uploaded',{'did':DID,'count':len(uploaded),'ids':uploaded})

# 4. parse all (batches)
for i in range(0,len(uploaded),50):
    pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':uploaded[i:i+50]},timeout=60).json()
    print(f'  parse trigger batch {i}: code={pr.get("code")}')
print(f'NEW_DID={DID}')
print(f'parse started for {len(uploaded)} docs. Polling...')

# 5. poll until done
t0=time.time(); last=-1
while time.time()-t0 < 6*3600:
    dd=[];page=1
    while True:
        rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
        b=rr['data']['docs']
        if not b: break
        dd.extend(b); page+=1
    from collections import Counter
    st=Counter(str(x['run']) for x in dd)
    done=st.get('3',0)+st.get('DONE',0); fail=st.get('4',0)+st.get('FAIL',0)
    if done!=last:
        el=int(time.time()-t0)
        print(f'  [{el//60}m] DONE={done}/{len(dd)} FAIL={fail} | {dict(st)}')
        last=done
    if done+fail>=len(dd): print('PARSE COMPLETE'); break
    time.sleep(30)
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
print(f'final chunks={d.get("chunk_count")}  embedding={d.get("embedding_model")}')
save('hozrim_qwen_done',{'did':DID,'chunks':d.get('chunk_count')})
