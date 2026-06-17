import sys, json, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c9a52c3467df11f18848750a2917932a'   # HOZRIM_NEW

def sql(q):
    return subprocess.run(['docker','exec','docker-mysql-1','mysql','-uroot','-pinfini_rag_flow','rag_flow','-e',q],
        capture_output=True,text=True)

# 1. HOZRIM_NEW: remove auto-keyword/question (fast parse), set enrichment llm = gemma4:26b
sql(f"update knowledgebase set parser_config=JSON_SET(parser_config,'$.auto_keywords',0,'$.auto_questions',0,'$.llm_id','gemma4:26b@Ollama') where id='{DID}'")
# also at document level (docs inherited the old config)
sql(f"update document set parser_config=JSON_SET(parser_config,'$.auto_keywords',0,'$.auto_questions',0,'$.llm_id','gemma4:26b@Ollama') where kb_id='{DID}'")

# verify
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('=== HOZRIM_NEW after update ===')
print('  chunk_token_num:',pc.get('chunk_token_num'),'parent_child:',pc.get('parent_child',{}).get('use_parent_child'))
print('  auto_keywords:',pc.get('auto_keywords'),'auto_questions:',pc.get('auto_questions'),'(0 = fast parse)')
print('  enrichment llm_id:',pc.get('llm_id'))
print('  embedding:',d.get('embedding_model'),'| files:',d.get('document_count'),'| graphrag:',pc.get('graphrag',{}).get('use_graphrag'))
