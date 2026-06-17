import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='aea56f0467b511f1a56521ba47a3a9e1'

cases=[
 ('20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪',
   'כן בתנאים: פרטי מ-10,000 חודשי, עסקי מ-25,000; חריגה מעל 10,000 או 25%'),
 ('12917','מהן סמכויות האישור של פקיד מורשה','המידע אינו קיים במערכת'),
 ('78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?',
   'חשמונאים(361), אפק(348), כפר גנים(317), אשקלון ברנע(349), רמת השרון(375)'),
]
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "אם המידע אינו מופיע במפורש — אמור 'המידע אינו קיים במאגר'.")
chat=requests.post(f'{BASE}/chats',headers=HJ,json={"name":f"test3ready_{int(time.time())}",
  "dataset_ids":[DID],"llm_id":"gpt-oss:20b@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","quote":True,"keyword":True,
    "cross_languages":["Hebrew","English"]}},timeout=30).json()['data']['id']
print('full settings: Qwen embed + Qwen rerank + chunk512 + auto-kw/q + gpt-oss:20b\n', flush=True)
out=[]
for proc,q,exp in cases:
    sid=requests.post(f'{BASE}/chats/{chat}/sessions',headers=HJ,json={"name":proc},timeout=30).json()['data']['id']
    try:
        rr=requests.post(f'{BASE}/chats/{chat}/completions',headers=HJ,
            json={"question":q,"stream":False,"session_id":sid},timeout=600).json()
        ans=(rr.get('data') or {}).get('answer','') if rr.get('code')==0 else f"ERR:{rr.get('message','')[:80]}"
    except Exception as e:
        ans=f'TIMEOUT/{str(e)[:50]}'
    print('='*85)
    print(f'nohal {proc}: {q[:50]}')
    print(f'  EXPECTED: {exp[:90]}')
    print(f'  ANSWER:   {ans[:280]}'.replace(chr(10),' '), flush=True)
    out.append({"proc":proc,"question":q,"expected":exp,"answer":ans})
save('test3ready_results',out)
print('\nDONE', flush=True)
