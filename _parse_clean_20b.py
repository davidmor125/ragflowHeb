import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='aea56f0467b511f1a56521ba47a3a9e1'

def docs():
    for _ in range(8):
        try: return requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=120).json()['data']['docs']
        except Exception: time.sleep(8)
    return []
ids=[x['id'] for x in docs()]
requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':ids},timeout=60)
print(f'parsing {len(ids)} files, gpt-oss:20b (clean, VRAM freed)...', flush=True)
t0=time.time(); last=None; stall=0
while time.time()-t0<5400:
    dd=docs()
    if not dd: time.sleep(20); continue
    from collections import Counter
    st=Counter(str(x['run']) for x in dd)
    done=st.get('DONE',0)+st.get('3',0); fail=st.get('FAIL',0)+st.get('4',0)
    chunks=sum(x.get('chunk_count',0) for x in dd)
    # show latest progress line per doc
    msgs=[]
    for x in dd:
        m=(x.get('progress_msg','') or '').strip().splitlines()
        msgs.append(f"{x['name'][:9]}:{round(x.get('progress',0),2)}")
    cur=(done,fail,chunks)
    if cur!=last:
        print(f'  [{int(time.time()-t0)}s] DONE={done} FAIL={fail} chunks={chunks} | {" ".join(msgs)}', flush=True)
        last=cur; stall=0
    else:
        stall+=1
    if done+fail>=len(dd):
        if fail:
            d0=[x for x in dd if str(x['run']) in ('FAIL','4')][0]
            print('FAIL:',(d0.get('progress_msg','') or '')[-200:])
        break
    time.sleep(25)
print('PARSE DONE', flush=True)
json.dump({'did':DID},open('_contract_out/check123_parsed.json','w'))
