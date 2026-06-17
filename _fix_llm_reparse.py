import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='aea56f0467b511f1a56521ba47a3a9e1'   # CHECKHOZRIMQWEN123

# set enrichment LLM to LOCAL gpt-oss:20b (cloud quota exhausted)
cfg={"chunk_token_num":512,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":3,"auto_questions":2,
     "llm_id":"gpt-oss:20b@Ollama",                # LOCAL enrichment model
     "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False},
     "parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
r=requests.put(f'{BASE}/datasets/{DID}',headers=HJ,json={"parser_config":cfg},timeout=30).json()
print('set enrichment llm to gpt-oss:20b@Ollama (local):',r.get('code'))

# verify
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('  llm_id now:',pc.get('llm_id'),'| chunk:',pc.get('chunk_token_num'),'auto_q:',pc.get('auto_questions'))

# re-parse the 4 docs
docs=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=30).json()['data']['docs']
ids=[x['id'] for x in docs]
requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':ids},timeout=30)
print(f'\nre-parsing {len(ids)} files with LOCAL llm (auto-keyword+question)...')
t0=time.time(); last=None
while time.time()-t0<3600:
    dd=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=30).json()['data']['docs']
    from collections import Counter
    st=Counter(str(x['run']) for x in dd)
    done=st.get('DONE',0)+st.get('3',0); fail=st.get('FAIL',0)+st.get('4',0)
    if (done,fail)!=last:
        print(f'  [{int(time.time()-t0)}s] DONE={done} FAIL={fail} of {len(dd)} | {dict(st)}')
        last=(done,fail)
    if done+fail>=len(dd):
        if fail:
            d0=[x for x in dd if str(x['run']) in ('FAIL','4')][0]
            print('FAIL msg:',(d0.get('progress_msg','') or '')[-300:])
        break
    time.sleep(15)
ds2=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d2=ds2['data'][0] if isinstance(ds2['data'],list) else ds2['data']
print(f'DONE: chunk_count={d2.get("chunk_count")}')
save('check123_parsed',{'did':DID,'chunks':d2.get('chunk_count')})
