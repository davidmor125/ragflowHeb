import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
SRC='c8482642674011f1a56221ba47a3a9e1'   # existing Qwen dataset to copy files from
FAILED_PROCS=['20071','20064','12917','78634']

# 1. create CHECKHOZRIMQWEN123 with ALL requested settings
cfg={
  "chunk_token_num":512,                          # chunk 512 (not 256)
  "delimiter":"\n",
  "layout_recognize":"DeepDOC",
  "auto_keywords":3,                              # rich metadata - keywords per chunk
  "auto_questions":2,                             # "smart question" per chunk
  "raptor":{"use_raptor":False},                  # no heavy graph/raptor
  "graphrag":{"use_graphrag":False},
  "parent_child":{"use_parent_child":True,"children_delimiter":"\n"},  # CHILD CHUNK
}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json={
    "name":"CHECKHOZRIMQWEN123",
    "embedding_model":"qwen3-embedding:4b@Ollama",   # Qwen embedding
    "chunk_method":"naive","parser_config":cfg},timeout=30).json()
if ds.get('code')!=0:
    print('CREATE FAIL:',ds); sys.exit(1)
DID=ds['data']['id']
print('CREATED dataset CHECKHOZRIMQWEN123:',DID)
print('  settings: Qwen embed, chunk=512, parent_child=ON, auto_keywords=3, auto_questions=2, graphrag=OFF')
save('check123_dataset',ds['data'])

# 2. download the 4 failed-procedure files from the Qwen dataset, upload to new
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{SRC}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
name2id={d['name']:d['id'] for d in docs}
uploaded=[]
for proc in FAILED_PROCS:
    fn=f'{proc}.html'
    src_id=name2id.get(fn)
    if not src_id:
        print(f'  {fn} not found in source'); continue
    content=requests.get(f'{BASE}/datasets/{SRC}/documents/{src_id}',headers=H,timeout=120).content
    up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,files={'file':(fn,content)},timeout=120).json()
    if up.get('code')==0:
        uploaded.append((proc,up['data'][0]['id']))
        print(f'  uploaded {fn} ({len(content)} bytes)')
ids=[i for _,i in uploaded]

# 3. parse (with auto-keyword/question this takes longer)
requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':ids},timeout=30)
print(f'\nparsing {len(ids)} files (auto-keyword+question -> slower)...')
t0=time.time(); last=None
while time.time()-t0<2400:
    dd=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=30).json()['data']['docs']
    from collections import Counter
    st=Counter(str(d['run']) for d in dd)
    done=st.get('DONE',0)+st.get('3',0); fail=st.get('FAIL',0)+st.get('4',0)
    if (done,fail)!=last:
        print(f'  [{int(time.time()-t0)}s] DONE={done} FAIL={fail} of {len(dd)} | {dict(st)}')
        last=(done,fail)
    if done+fail>=len(dd): break
    time.sleep(10)
ds2=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d2=ds2['data'][0] if isinstance(ds2['data'],list) else ds2['data']
print(f'PARSE DONE: chunk_count={d2.get("chunk_count")}')
save('check123_parsed',{'did':DID,'chunks':d2.get('chunk_count')})
print('DID='+DID)
