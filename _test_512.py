import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
SRC='c8482642674011f1a56221ba47a3a9e1'

# 1. find + download 20071.html from the existing Qwen dataset
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{SRC}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
src_doc={d['name']:d['id'] for d in docs}['20071.html']
content=requests.get(f'{BASE}/datasets/{SRC}/documents/{src_doc}',headers=H,timeout=120).content
print(f'downloaded 20071.html: {len(content)} bytes')

# 2. create small dataset: Qwen embedding, chunk 512, parent_child, no graph/raptor
cfg={"chunk_token_num":512,"delimiter":"\n","layout_recognize":"DeepDOC",
     "auto_keywords":0,"auto_questions":0,"raptor":{"use_raptor":False},
     "graphrag":{"use_graphrag":False},"parent_child":{"use_parent_child":True,"children_delimiter":"\n"}}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json={
    "name":f"test512_{int(time.time())}","embedding_model":"qwen3-embedding:4b@Ollama",
    "chunk_method":"naive","parser_config":cfg},timeout=30).json()
DID=ds['data']['id']
print('dataset (chunk 512):',DID)

# 3. upload + parse
up=requests.post(f'{BASE}/datasets/{DID}/documents',headers=H,
    files={'file':('20071.html',content)},timeout=120).json()
doc=up['data'][0]['id']
requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':[doc]},timeout=30)
t0=time.time()
while time.time()-t0<600:
    d=requests.get(f'{BASE}/datasets/{DID}/documents?id={doc}',headers=H,timeout=30).json()['data']['docs'][0]
    if str(d['run']) in ('DONE','3') and d.get('progress',0)>=1: break
    if str(d['run']) in ('FAIL','4'): print('PARSE FAIL'); sys.exit(1)
    time.sleep(8)
print(f'parsed: chunk_count={d.get("chunk_count")} (chunk 512)')

# 4. ask Q4 with same setup
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "אם המידע אינו מופיע במפורש — אמור 'המידע אינו קיים במאגר'.")
chat=requests.post(f'{BASE}/chats',headers=HJ,json={"name":f"t512_{int(time.time())}",
  "dataset_ids":[DID],"llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"x","quote":True,"keyword":True,"cross_languages":["Hebrew","English"]}},timeout=30).json()['data']['id']
sid=requests.post(f'{BASE}/chats/{chat}/sessions',headers=HJ,json={"name":"q4"},timeout=30).json()['data']['id']
q='במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"'
rr=requests.post(f'{BASE}/chats/{chat}/completions',headers=HJ,
    json={"question":q,"stream":False,"session_id":sid},timeout=900).json()
ans=(rr.get('data') or {}).get('answer','')
chunks=(rr.get('data') or {}).get('reference',{}).get('chunks',[])
print('\n=== Q4 with chunk 512 ===')
print('EXPECTED: הפעולה אינה חייבת בדיווח; תיעוד תיאור המקרה והבדיקות')
print('ANSWER:',ans[:300].replace('\n',' '))
print('\ntop retrieved chunk:',chunks[0]['content'][:150].replace('\n',' ') if chunks else 'none')
print('answer contains "אינה חייבת":', 'אינה חייבת' in ans)
save('test512_q4',{'answer':ans,'chunk_count':d.get('chunk_count')})
