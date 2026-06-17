import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

# read the new dataset id
DID=json.load(open(f'{OUT}/check123_parsed.json',encoding='utf-8'))['did']
print('testing on CHECKHOZRIMQWEN123:',DID)

# the 4 failed questions (Q4/Q5 same -> one), with expected
cases=[
 ('20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
   'לאחר בדיקת הסניף נמצא כי הפעולה אינה חייבת בדיווח; יש לפרט תיאור המקרה, הבדיקות והסיבות; בבחירת "תקין" נפתחת רשימת סיבות'),
 ('20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪',
   'כן, בתנאים: חשבון פרטי הפקדות חודשיות מ-10,000₪, עסקי מ-25,000₪; חריגה מעל 10,000₪ או 25%'),
 ('12917','מהן סמכויות האישור של פקיד מורשה','המידע אינו קיים במערכת'),
 ('78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?',
   'חשמונאים(361), אפק(348), כפר גנים(317), אשקלון ברנע(349), רמת השרון(375)'),
]

PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד אך ורק על סמך:\n{knowledge}\n"
     "חשוב: אם המידע הספציפי אינו מופיע במפורש במאגר — אמור 'המידע אינו קיים במאגר'. אל תמציא ואל תנחש.")
chat=requests.post(f'{BASE}/chats',headers=HJ,json={"name":f"check123test_{int(time.time())}",
  "dataset_ids":[DID],"llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","quote":True,"keyword":True,
    "cross_languages":["Hebrew","English"]}},timeout=30).json()['data']['id']
print('assistant: Qwen embed + Qwen rerank + GEMMA + top_n=8\n')

out=[]
for proc,q,exp in cases:
    sid=requests.post(f'{BASE}/chats/{chat}/sessions',headers=HJ,json={"name":proc},timeout=30).json()['data']['id']
    rr=requests.post(f'{BASE}/chats/{chat}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=900).json()
    ans=(rr.get('data') or {}).get('answer','')
    print('='*88)
    print(f'נוהל {proc}: {q[:55]}')
    print(f'  EXPECTED: {exp[:95]}')
    print(f'  ANSWER:   {ans[:240]}'.replace(chr(10),' '))
    out.append({"proc":proc,"question":q,"expected":exp,"answer":ans})
save('check123_retest_results',out)
print('\nDONE - I (Fable) will judge each.')
