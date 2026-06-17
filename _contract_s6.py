import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'
CHAT='e382caaa661b11f1ae84bd00f07a0952'
HEB=("אתה עוזר ידע מדויק. ענה בעברית בלבד, אך ורק על סמך המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור במפורש שאינך יודע. אל תמציא מידע.")

# enable cross-language retrieval on the assistant (Hebrew+English)
upd={"prompt_config":{"system":HEB,"parameters":[{"key":"knowledge","optional":False}],
   "empty_response":"","prologue":"שלום!","quote":True,"refine_multiturn":False,"tts":False,
   "cross_languages":["Hebrew","English"]}}
r=requests.put(f'{BASE}/chats/{CHAT}',headers=HJ,json=upd,timeout=30).json()
print('enable cross_languages on chat:',r.get('code'))
save('s6_chat_crosslang_update',{'request':upd,'response':r})

se=requests.post(f'{BASE}/chats/{CHAT}/sessions',headers=HJ,json={"name":"acceptance"},timeout=30).json()
sid=se['data']['id']
print('acceptance session:',sid)

QS=[
 ("q1_paragraph","מהו מודל ההטמעה של המערכת ומה מאפיין אותו?",["bge-m3"],"[כותרת-ראשית: מסמך-בדיקה-12345]"),
 ("q2_table","מהו הקוד הסודי המופיע בטבלת המפרט הטכני?",["ZX9871"],"ZX9871"),
 ("q3_mermaid","איזה מפתח מופיע בתרשים הזרימה בשלב ניסוח התשובה?",["MERMAIDKEY42"],"MERMAIDKEY42"),
 ("q4_image","לפי תרשים המכירות, באיזה רבעון נרשם השיא ומה הערך?",["Q4"],"260"),
]
results=[]
for name,q,expect,ref_marker in QS:
    t0=time.time()
    r=requests.post(f'{BASE}/chats/{CHAT}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=900).json()
    dt=time.time()-t0
    d=r.get('data') or {}
    ans=d.get('answer',''); chunks=(d.get('reference') or {}).get('chunks',[])
    ok_ans=all(e in ans for e in expect)
    ok_ref=any(ref_marker in c.get('content','') for c in chunks)
    heb=any('א'<=ch<='ת' for ch in ans)
    print(f'{name}: {dt:.0f}s answer_ok={ok_ans} ref_has_marker={ok_ref} hebrew={heb}')
    print(f'   A: {ans[:160]}'.replace(chr(10),' '))
    save(f's6_{name}_response',r)
    results.append({"name":name,"question":q,"seconds":round(dt,1),"answer_ok":ok_ans,
                    "ref_marker_ok":ok_ref,"hebrew":heb,"answer":ans[:300],
                    "ref_chunk_ids":[c.get('id') for c in chunks]})
save('s6_acceptance_summary',results)
passed=sum(1 for x in results if x['answer_ok'] and x['ref_marker_ok'])
print(f'ACCEPTANCE: {passed}/{len(results)} passed')
