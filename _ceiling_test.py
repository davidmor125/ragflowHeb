import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='c8482642674011f1a56221ba47a3a9e1'

# 5 wrong Qs with their CORRECT procedure
cases=[
 (4,'20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
   'הפעולה אינה חייבת בדיווח; תיעוד תיאור המקרה והבדיקות'),
 (5,'20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
   'הפעולה אינה חייבת בדיווח; תיעוד תיאור המקרה והבדיקות'),
 (7,'20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪',
   'כן בתנאים: פרטי 10,000₪, עסקי 25,000₪'),
 (9,'12917','מהן סמכויות האישור של פקיד מורשה','המידע אינו קיים'),
 (12,'78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?','חשמונאים361,אפק348,כפר גנים317...'),
]
# map proc->docid
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
p2id={d['name'].replace('.html',''):d['id'] for d in docs}

PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "אם המידע הספציפי אינו מופיע במפורש — אמור 'המידע אינו קיים במאגר'. אל תמציא.")
body={"name":f"ceiling_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","prologue":"x","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
cid=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()['data']['id']
print('CEILING test: retrieval RESTRICTED to the correct procedure doc\n')

out=[]
for n,proc,q,exp in cases:
    docid=p2id.get(proc)
    se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":f"q{n}"},timeout=30).json()
    sid=se['data']['id']
    # restrict via document_ids in the completion
    rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid,"document_ids":[docid]},timeout=900).json()
    ans=(rr.get('data') or {}).get('answer','')
    print('='*85)
    print(f'Q{n} [נוהל {proc}]')
    print(f'  EXPECTED: {exp}')
    print(f'  ANSWER (restricted to {proc}): {ans[:200]}'.replace(chr(10),' '))
    out.append({"n":n,"proc":proc,"question":q,"expected":exp,"answer":ans})
save('ceiling_results',out)
print('\nDONE - I (Fable) judge.')
