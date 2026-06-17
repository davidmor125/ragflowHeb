import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'; DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'
pr=requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[DOC]},timeout=30).json()
print('parse trigger:',pr.get('code'))
t0=time.time(); last=None
while time.time()-t0<2400:
    d=requests.get(f'{BASE}/datasets/{DID}/documents?id={DOC}',headers=H,timeout=30).json()['data']['docs'][0]
    run,prog=str(d['run']),round(d.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} prog={prog} chunks={d.get("chunk_count",0)}')
        last=(run,prog)
    if run in ('3','DONE') and d.get('progress',0)>=1:
        print('DONE chunks=',d.get('chunk_count')); break
    if run in ('4','FAIL'):
        print('FAIL:',(d.get('progress_msg','') or '')[-200:]); break
    time.sleep(8)
