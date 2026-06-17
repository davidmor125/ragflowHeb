import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
SRC='c8482642674011f1a56221ba47a3a9e1'   # existing Qwen dataset (646 files) to copy from

# 1. create HOZRIM_NEW with FULL settings (enrichment LLM = LOCAL 20b)
cfg={
  "chunk_token_num":512,
  "delimiter":"\n",
  "layout_recognize":"DeepDOC",
  "auto_keywords":3,
  "auto_questions":2,
  "raptor":{"use_raptor":False},
  "graphrag":{"use_graphrag":False},
  "parent_child":{"use_parent_child":True,"children_delimiter":"\n"},
}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json={
    "name":"HOZRIM_NEW",
    "embedding_model":"qwen3-embedding:4b@Ollama",
    "chunk_method":"naive","parser_config":cfg},timeout=30).json()
if ds.get('code')!=0:
    print('CREATE FAIL:',ds); sys.exit(1)
DID=ds['data']['id']
print('CREATED HOZRIM_NEW:',DID, flush=True)
save('hozrim_new_dataset',ds['data'])
# set enrichment llm_id to local 20b directly in DB (API rejects it in parser_config)
import subprocess
subprocess.run(['docker','exec','docker-mysql-1','mysql','-uroot','-pinfini_rag_flow','rag_flow','-e',
  f"update knowledgebase set parser_config=JSON_SET(parser_config,'$.llm_id','gpt-oss:20b@Ollama') where id='{DID}'"],
  capture_output=True)
print('  set enrichment llm_id=gpt-oss:20b@Ollama (local)', flush=True)

# 2. copy ALL files from existing Qwen dataset (NO parse)
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{SRC}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
print(f'source has {len(docs)} files, copying (no parse)...', flush=True)
uploaded=0
for i,d in enumerate(docs,1):
    try:
        content=requests.get(f'{BASE}/datasets/{SRC}/documents/{d["id"]}',headers=H,timeout=120).content
        up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,
            files={'file':(d['name'],content)},timeout=120).json()
        if up.get('code')==0: uploaded+=1
    except Exception as e:
        print(f'  [{i}] {d["name"]} err:',str(e)[:40])
    if i%100==0: print(f'  copied {i}/{len(docs)}', flush=True)
print(f'\nDONE: HOZRIM_NEW has {uploaded} files uploaded, NOT parsed.', flush=True)
print('To parse at night: open HOZRIM_NEW in UI and click parse, OR run parse via API.')
print('HOZRIM_NEW_DID='+DID)
save('hozrim_new_ready',{'did':DID,'files':uploaded})
