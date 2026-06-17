import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
# list all datasets, show which are Qwen vs bge
r=requests.get(f'{BASE}/datasets?page=1&page_size=50',headers=H,timeout=30).json()
data=r.get('data')
dss = data if isinstance(data,list) else (data.get('kbs') or [])
print('=== all datasets ===')
for d in dss:
    nm=d.get('name','')
    if 'hozrim' in nm or 'qwen' in nm.lower():
        print(f"  {nm[:40]:40s} | embedding={d.get('embedding_model')} | docs={d.get('document_count')} chunks={d.get('chunk_count')} | id={d.get('id')}")
