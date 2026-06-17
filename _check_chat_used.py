import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
r=requests.get('http://localhost:9380/api/v1/chats?page=1&page_size=50',headers=H,timeout=30).json()
data=r.get('data')
chats = data if isinstance(data,list) else (data.get('chats') or data.get('items') or [])
print('chats found:',len(chats))
for c in chats:
    nm=c.get('name','')
    if 'hozrim132' in nm or 'eval' in nm:
        print(f"{nm}: llm={c.get('llm_id')} rerank={c.get('rerank_id')} top_n={c.get('top_n')}")
