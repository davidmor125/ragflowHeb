import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='c8482642674011f1a56221ba47a3a9e1'   # Qwen-embedding clone of hozrim

qs=json.load(open('test_questions_full.json',encoding='utf-8'))
print(f'{len(qs)} questions | dataset={DID} | Qwen embed + Qwen rerank + top_n=8\n')

# --- assistant ---
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור 'לא נמצא מידע במאגר'. אל תמציא מידע.")
body={"name":f"hozrim132j_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"לא נמצא מידע במאגר","prologue":"שלום","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
assert r.get('code')==0, r
cid=r['data']['id']

# --- judge ---
JSYS=("אתה בודק איכות של מערכת שו\"ת על נהלים בנקאיים. נתונה שאלה, תשובת המערכת, "
     "והתשובה הנכונה. דרג: 'correct' אם תואם בעובדות המרכזיות, 'partial' אם חלקי, "
     "'wrong' אם שגוי או 'לא נמצא מידע'. החזר JSON: {\"verdict\":\"correct|partial|wrong\",\"reason\":\"...\"}")
def judge(q,ans,ref):
    u=f"שאלה: {q}\n\nתשובת המערכת: {ans}\n\nהתשובה הנכונה:\n{ref[:1500]}"
    try:
        r=requests.post(OLLAMA,json={"model":JUDGE,"messages":[{"role":"system","content":JSYS},
            {"role":"user","content":u}],"stream":False,"options":{"temperature":0}},timeout=300)
        t=re.sub(r'^.*</think>','',r.json()['message']['content'],flags=re.DOTALL)
        m=re.search(r'\{.*\}',t,re.DOTALL)
        if m: return json.loads(m.group(0))
    except Exception: pass
    return {"verdict":"wrong" if "לא נמצא" in ans else "partial","reason":"judge fail"}

out=[]; tally={'correct':0,'partial':0,'wrong':0}
for i,q in enumerate(qs,1):
    se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":f"q{i}"},timeout=30).json()
    sid=se['data']['id']
    try:
        rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
            json={"question":q['question'],"stream":False,"session_id":sid},timeout=900).json()
    except Exception as e:
        rr={'data':{'answer':''}}
    dd=rr.get('data') or {}
    ans=dd.get('answer','') if isinstance(dd,dict) else ''
    v=judge(q['question'],ans,q.get('expected_answer',''))
    verdict=v.get('verdict','partial')
    tally[verdict]=tally.get(verdict,0)+1
    out.append({"n":i,"procedure":str(q.get('procedure','')),"topic":q.get('topic'),
                "question":q['question'],"answer":ans,"verdict":verdict,
                "reason":v.get('reason','')[:140],"expected_answer":q.get('expected_answer','')})
    save('hozrim132j_partial',out)
    # per-20 status with AI-judge results
    if i%20==0 or i==len(qs):
        print(f'=== after {i} questions ===')
        print(f'  correct={tally["correct"]}  partial={tally["partial"]}  wrong={tally["wrong"]}')
        last20=out[-20:] if i%20==0 else out[-(i%20 or 20):]
        wrongs=[x for x in last20 if x['verdict']=='wrong']
        if wrongs:
            print(f'  FAILED in this batch:')
            for w in wrongs: print(f'    Q{w["n"]} [{w["topic"]}/{w["procedure"]}]: {w["reason"][:80]}')
        sys.stdout.flush()

save('hozrim132j_results',out)
n=len(out)
print(f'\n====== FINAL: {n} questions ======')
print(f'correct={tally["correct"]}/{n} ({tally["correct"]*100//n}%)  partial={tally["partial"]}  wrong={tally["wrong"]}')
print(f'correct+partial={tally["correct"]+tally["partial"]}/{n} ({(tally["correct"]+tally["partial"])*100//n}%)')
