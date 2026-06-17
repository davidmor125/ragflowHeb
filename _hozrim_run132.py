import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='c8482642674011f1a56221ba47a3a9e1'   # new Qwen-embedding clone of hozrim

qs=json.load(open('test_questions_full.json',encoding='utf-8'))
print(f'{len(qs)} questions loaded')

# Full Qwen stack: Qwen embedding (dataset) + Qwen reranker + top_n=8
PROMPT=("אתה עוזר שעונה על שאלות לגבי נהלים בנקאיים. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור 'לא נמצא מידע במאגר'. אל תמציא מידע.")
body={"name":f"hozrim132_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"לא נמצא מידע במאגר","prologue":"שלום","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
assert r.get('code')==0, r
cid=r['data']['id']
print('assistant:',cid,'(Qwen embed + Qwen rerank, top_n=8)')

out=[]
for i,q in enumerate(qs,1):
    se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":f"q{i}"},timeout=30).json()
    sid=se['data']['id']
    t0=time.time()
    try:
        rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
            json={"question":q['question'],"stream":False,"session_id":sid},timeout=900).json()
    except Exception as e:
        rr={'code':-1,'message':str(e)}
    dt=time.time()-t0
    dd=rr.get('data') or {}
    ans=dd.get('answer','') if isinstance(dd,dict) else ''
    chunks=(dd.get('reference') or {}).get('chunks',[]) if isinstance(dd,dict) else []
    # did reference cite the expected source procedure?
    proc=str(q.get('procedure',''))
    hit=any(proc in (c.get('document_name','')+c.get('content','')) for c in chunks)
    no_info='לא נמצא מידע' in ans or not ans.strip()
    if i%10==0 or i<=3:
        print(f"Q{i:03d} {dt:4.0f}s proc={proc} hit={hit} | {ans[:50].replace(chr(10),' ')}")
    out.append({"n":i,"procedure":proc,"topic":q.get('topic'),"question":q['question'],
                "expected_answer":q.get('expected_answer',''),"answer":ans,
                "ref_hit":hit,"no_info":no_info,"seconds":round(dt,1)})
    save('hozrim132_partial',out)
save('hozrim132_results',out)
hits=sum(1 for x in out if x['ref_hit']); ni=sum(1 for x in out if x['no_info'])
print(f"\nDONE: ref_hit={hits}/{len(out)}  no_info={ni}/{len(out)}")
print('CHAT='+cid)
