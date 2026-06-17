import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'

PROMPT=("אתה עוזר שעונה על שאלות לגבי מסמך איפיון. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "כללים: ענה רק על הפרק שנשאל; כשהמקור טבלה — שחזר כל שורה; אם אין מידע — 'לא נמצא מידע במאגר'.")
body={"name":f"smoke31_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":3,
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"לא נמצא מידע במאגר","prologue":"שלום","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
if r.get('code')!=0:
    print('CREATE FAIL:',r); sys.exit(1)
cid=r['data']['id']
print('assistant created, persisted llm:',r['data'].get('llm_id'))

se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":"smoke"},timeout=30).json()
sid=se['data']['id']
q='איזה אינטגרציות עיקריות תומכת המערכת?'
t0=time.time()
try:
    rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=300).json()
except Exception as e:
    print('COMPLETION ERROR:',e); sys.exit(1)
dt=time.time()-t0
d=rr.get('data') or {}
ans=d.get('answer','') if isinstance(d,dict) else str(d)
chunks=(d.get('reference') or {}).get('chunks',[]) if isinstance(d,dict) else []
heb=any('א'<=c<='ת' for c in ans)
print(f'\nSMOKE RESULT ({dt:.0f}s):')
print('  code:',rr.get('code'))
print('  hebrew answer:',heb)
print('  ref chunks:',len(chunks))
print('  answer:',ans[:300].replace('\n',' '))
ok = rr.get('code')==0 and heb and len(ans.strip())>20 and 'לא נמצא מידע' not in ans
print('\n*** GEMMA 31b-cloud WORKS END-TO-END:',ok,'***')
print('CHAT_ID='+cid if ok else 'NOT_OK')
