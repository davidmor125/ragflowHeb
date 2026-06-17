import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='aea56f0467b511f1a56521ba47a3a9e1'   # CHECKHOZRIMQWEN123 (llm_id now gpt-oss:120b@Ollama local)

# 1. re-parse 4 docs (enrichment now uses local 120b)
docs=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=30).json()['data']['docs']
ids=[x['id'] for x in docs]
requests.post(f'{BASE}/datasets/{DID}/chunks',headers=HJ,json={'document_ids':ids},timeout=30)
print(f're-parsing {len(ids)} files with LOCAL gpt-oss:120b (auto-keyword+question)...')
t0=time.time(); last=None
while time.time()-t0<5400:
    dd=requests.get(f'{BASE}/datasets/{DID}/documents?page=1&page_size=50',headers=H,timeout=30).json()['data']['docs']
    from collections import Counter
    st=Counter(str(x['run']) for x in dd)
    done=st.get('DONE',0)+st.get('3',0); fail=st.get('FAIL',0)+st.get('4',0)
    if (done,fail)!=last:
        print(f'  [{int(time.time()-t0)}s] DONE={done} FAIL={fail} of {len(dd)} | {dict(st)}', flush=True)
        last=(done,fail)
    if done+fail>=len(dd):
        if fail:
            d0=[x for x in dd if str(x['run']) in ('FAIL','4')][0]
            print('FAIL msg:',(d0.get('progress_msg','') or '')[-300:])
        break
    time.sleep(20)
ds2=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d2=ds2['data'][0] if isinstance(ds2['data'],list) else ds2['data']
print(f'PARSE DONE: chunk_count={d2.get("chunk_count")}\n')

# 2. test 4 failed questions with LOCAL 120b answers + Qwen rerank
cases=[
 ('20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
   'לאחר בדיקת הסניף נמצא כי הפעולה אינה חייבת בדיווח; יש לפרט תיאור המקרה, הבדיקות והסיבות; בבחירת "תקין" נפתחת רשימת סיבות'),
 ('20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪',
   'כן, בתנאים: חשבון פרטי מ-10,000₪ חודשי, עסקי מ-25,000₪; חריגה מעל 10,000₪ או 25%'),
 ('12917','מהן סמכויות האישור של פקיד מורשה','המידע אינו קיים במערכת'),
 ('78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?',
   'חשמונאים(361), אפק(348), כפר גנים(317), אשקלון ברנע(349), רמת השרון(375)'),
]
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "חשוב: אם המידע הספציפי אינו מופיע במפורש — אמור 'המידע אינו קיים במאגר'. אל תמציא ואל תנחש.")
chat=requests.post(f'{BASE}/chats',headers=HJ,json={"name":f"check123_local120_{int(time.time())}",
  "dataset_ids":[DID],"llm_id":"gpt-oss:120b@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","quote":True,"keyword":True,
    "cross_languages":["Hebrew","English"]}},timeout=30).json()['data']['id']
print('assistant: Qwen embed + Qwen rerank + LOCAL gpt-oss:120b + top_n=8\n')
out=[]
for proc,q,exp in cases:
    sid=requests.post(f'{BASE}/chats/{chat}/sessions',headers=HJ,json={"name":proc},timeout=30).json()['data']['id']
    rr=requests.post(f'{BASE}/chats/{chat}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=1200).json()
    ans=(rr.get('data') or {}).get('answer','')
    print('='*88)
    print(f'נוהל {proc}: {q[:55]}')
    print(f'  EXPECTED: {exp[:95]}')
    print(f'  ANSWER:   {ans[:260]}'.replace(chr(10),' '), flush=True)
    out.append({"proc":proc,"question":q,"expected":exp,"answer":ans})
save('check123_local120_results',out)
print('\nDONE - judge.')
