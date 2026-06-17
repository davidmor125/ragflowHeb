import sys, json, requests
sys.stdout.reconfigure(encoding='utf-8')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='dc0091ca46e211f196f633ac796a3d7a'
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
running=[x['id'] for x in docs if str(x['run']) in ('2','RUNNING','1')]
print('running docs to stop:',len(running))
for i in range(0,len(running),50):
    r=requests.delete(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':running[i:i+50]},timeout=120).json()
    print('  stop batch',i,'code=',r.get('code'))
# recheck
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
from collections import Counter
print('states after stop:',dict(Counter(str(x['run']) for x in docs)))
