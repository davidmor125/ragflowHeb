import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
for did,label in [('dc0091ca46e211f196f633ac796a3d7a','OLD hozrim (browser)'),
                  ('c8482642674011f1a56221ba47a3a9e1','NEW hozrim_qwen (tested)')]:
    r=requests.get(f'{BASE}/datasets?id={did}',headers=H,timeout=30).json()
    d=r['data'][0] if isinstance(r['data'],list) else r['data']
    pc=d.get('parser_config',{})
    print(f'{label}:')
    print(f"  name={d.get('name')}  embedding={d.get('embedding_model')}")
    print(f"  graphrag={pc.get('graphrag',{}).get('use_graphrag')}  parent_child={pc.get('parent_child',{}).get('use_parent_child')}  chunks={d.get('chunk_count')}")
    print()
