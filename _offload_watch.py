import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
r=requests.get(f'{BASE}/datasets?page_size=50',headers=H,timeout=30).json()
for d in r['data']:
    if d['name'].startswith('client_offload'):
        docs=requests.get(f"{BASE}/datasets/{d['id']}/documents?page_size=10",headers=H,timeout=30).json()
        for doc in docs['data']['docs']:
            print(d['name'],'|',doc['name'],'| run=',doc['run'],'| progress=',round(doc.get('progress',0),3),
                  '| chunks=',doc.get('chunk_count',0))
            msg=doc.get('progress_msg','')
            if msg: print('   last:',msg.strip().splitlines()[-1][:160])
