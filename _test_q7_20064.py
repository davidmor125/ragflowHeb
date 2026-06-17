import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='aea56f0467b511f1a56521ba47a3a9e1'

# restrict to 20064 doc (only one fully parsed)
docs=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=60).json()['data']['docs']
doc20064=[d['id'] for d in docs if d['name']=='20064.html' and str(d['run']) in ('DONE','3')]
print('20064 ready:',bool(doc20064))

q='האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪'
exp='כן בתנאים: חשבון פרטי הפקדות חודשיות מ-10,000₪, עסקי מ-25,000₪; חריגה מעל 10,000₪ או 25%'

# First: does retrieval (with all settings: auto-keyword/question chunks + Qwen rerank) surface the answer?
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'document_ids':doc20064,'page_size':8,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
    'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=120).json()
ch=r['data']['chunks']
print(f'\nretrieved {len(ch)} chunks. Does any contain 10,000 / 25,000?')
for i,c in enumerate(ch):
    has10=('10,000' in c['content'] or '10000' in c['content'])
    has25=('25,000' in c['content'] or '25000' in c['content'])
    mark=' <<10k' if has10 else ('  <<25k' if has25 else '')
    print(f'  rank{i+1} sim={c.get("similarity",0):.3f}{mark} | {c["content"][:50].replace(chr(10)," ")}')
    # show keywords/questions metadata if present
    if c.get('important_keywords') or c.get('questions'):
        print(f'      keywords={c.get("important_keywords",[])[:3]} questions={[x[:30] for x in c.get("questions",[])[:1]]}')

# Now: answer with gpt-oss:20b + the full-enrichment chunks
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "אם המידע אינו מופיע במפורש — אמור 'המידע אינו קיים במאגר'.")
chat=requests.post(f'{BASE}/chats',headers=HJ,json={"name":f"q7test_{int(time.time())}",
  "dataset_ids":[DID],"llm_id":"gpt-oss:20b@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","quote":True,"keyword":True,
    "cross_languages":["Hebrew","English"]}},timeout=30).json()['data']['id']
sid=requests.post(f'{BASE}/chats/{chat}/sessions',headers=HJ,json={"name":"q7"},timeout=30).json()['data']['id']
rr=requests.post(f'{BASE}/chats/{chat}/completions',headers=HJ,
    json={"question":q,"stream":False,"session_id":sid,"document_ids":doc20064},timeout=900).json()
ans=(rr.get('data') or {}).get('answer','')
print(f'\n=== Q7 ANSWER (full settings, 20064) ===')
print('EXPECTED:',exp)
print('ANSWER:  ',ans[:300].replace('\n',' '))
print('\ncontains 10,000:', '10,000' in ans or '10000' in ans)
print('contains 25,000:', '25,000' in ans or '25000' in ans)
