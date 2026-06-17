"""
RAGFLOW Service Contract — live verification harness.
Captures real request/response JSON for each capability into _contract_out/.
Hebrew is sent via python requests (shell-curl breaks Hebrew, verified).
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE = 'http://localhost:9380/api/v1'
LEGACY = 'http://localhost:9380/v1'   # legacy app (llm registration, document/run)
KEY = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H = {'Authorization': f'Bearer {KEY}'}
HJ = {**H, 'Content-Type': 'application/json'}
OUT = '_contract_out'
os.makedirs(OUT, exist_ok=True)

def save(name, obj):
    with open(f'{OUT}/{name}.json', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def post(url, **kw):
    return requests.post(url, **kw)

def section1_create_full_pipeline():
    """Create dataset with the full enrichment pipeline via API only."""
    body = {
        "name": "contract_full_pipeline_" + str(int(time.time())),
        "embedding_model": "bge-m3@Ollama",
        "chunk_method": "naive",
        "parser_config": {
            "chunk_token_num": 512,
            "delimiter": "\\n!?;。;！？",
            "layout_recognize": "DeepDOC",
            "auto_keywords": 3,        # Keyword enrichment
            "auto_questions": 2,       # Question enrichment
            "raptor": {"use_raptor": True},   # Summary (recursive) enrichment
            "graphrag": {"use_graphrag": False},
            "html4excel": False
        },
        "auto_metadata_config": {      # Metadata enrichment (top-level)
            "enabled": True,
            "fields": [
                {"name": "topic", "type": "string", "description": "נושא המסמך"},
                {"name": "doc_date", "type": "time", "description": "תאריך המסמך"}
            ]
        }
    }
    r = post(f'{BASE}/datasets', headers=HJ, json=body, timeout=30)
    j = r.json()
    save('s1_create_request', body)
    save('s1_create_response', j)
    print('S1 create code=%s id=%s' % (j.get('code'), j.get('data', {}).get('id')))
    if j.get('code') != 0:
        print('   ERROR:', j.get('message'))
        return None
    did = j['data']['id']
    # read it back to confirm what the server stored
    rg = requests.get(f'{BASE}/datasets?id={did}', headers=H, timeout=20).json()
    save('s1_readback', rg)
    stored = rg['data'][0] if rg.get('data') else {}
    print('   stored parser_config:', json.dumps(stored.get('parser_config', {}), ensure_ascii=False)[:400])
    return did

if __name__ == '__main__':
    fn = sys.argv[1] if len(sys.argv) > 1 else 'section1_create_full_pipeline'
    globals()[fn]()
