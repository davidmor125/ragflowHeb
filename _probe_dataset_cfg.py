import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'

ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
print('=== DATASET top-level settings ===')
for k in ['chunk_method','embedding_model','parser_id','chunk_count','document_count']:
    print(f'  {k}: {d.get(k)}')
print('\n=== parser_config (THE chunking settings) ===')
print(json.dumps(d.get('parser_config',{}),ensure_ascii=False,indent=2))
