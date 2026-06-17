import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='c8482642674011f1a56221ba47a3a9e1'

# the 5 wrong, with their expected answers (truncated)
fails=[
 (4,'במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
    'לאחר בדיקת הסניף נמצא כי הפעולה אינה חייבת בדיווח; יש לתעד תיאור המקרה, הבדיקות והסיבות, לסרוק מסמכים; בבחירת "תקין" נפתחת רשימת סיבות'),
 (5,'במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"',
    'לאחר בדיקת הסניף נמצא כי הפעולה אינה חייבת בדיווח; יש לתעד תיאור המקרה, הבדיקות והסיבות'),
 (7,'האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪',
    'כן, אם מתקיימים תנאים: חשבון פרטי הפקדות חודשיות מ-10,000 ₪, עסקי מ-25,000 ₪; חריגה מעל 10,000 ₪ או 25%'),
 (9,'מהן סמכויות האישור של פקיד מורשה',
    'המידע אינו קיים במערכת'),
 (12,'מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?',
    'חשמונאים(361) אוצה"ח חשמונאים; אפק(348); כפר גנים(317); אשקלון ברנע(349); רמת השרון(375)'),
]

# FIX: top_n=20 + anti-hallucination prompt
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "חשוב מאוד: אם המידע הספציפי הנדרש לתשובה אינו מופיע במפורש במאגר — אמור 'המידע אינו קיים במאגר' "
     "ואל תמציא, אל תנחש, ואל תשלים מהקשר כללי. ענה רק על מה שכתוב במפורש.")
body={"name":f"retest5_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":20,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"המידע אינו קיים במאגר","prologue":"שלום","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
assert r.get('code')==0, r
cid=r['data']['id']
print('FIX config: top_n=20 + anti-hallucination prompt + Qwen embed/rerank\n')

out=[]
for n,q,exp in fails:
    se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":f"q{n}"},timeout=30).json()
    sid=se['data']['id']
    rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=900).json()
    ans=(rr.get('data') or {}).get('answer','')
    print('='*85)
    print(f'Q{n}: {q[:60]}')
    print(f'  EXPECTED: {exp[:90]}')
    print(f'  NEW ANSWER: {ans[:200]}'.replace(chr(10),' '))
    out.append({"n":n,"question":q,"expected":exp,"new_answer":ans})
save('retest5_results',out)
print('\nDONE - I (Fable) will judge these.')
