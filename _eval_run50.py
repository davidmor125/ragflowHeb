import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DID='3db1df6c669d11f1b9e5df329cd4ee1f'
MODEL='gpt-oss:20b@Ollama'

# ---- parse the questions file ----
raw=open('_client_eval_questions.md',encoding='utf-8').read()
blocks=re.split(r'\n## שאלה \d+\n',raw)[1:]
items=[]
for i,b in enumerate(blocks,1):
    qm=re.search(r'\*\*השאלה:\*\*\s*(.+)',b)
    sec=re.search(r'\[S(\d+):',b)
    expected=re.search(r'\(idx=\d+,\s*sectionId=([^\)]+)\)',b)
    body=b.split('**הפרק שאמור לענות',1)[-1]
    items.append({"n":i,"question":qm.group(1).strip() if qm else None,
                  "expected_section":f"S{sec.group(1)}" if sec else None,
                  "expected_text":body.strip()[:1500]})
print('parsed questions:',len(items))
assert all(x['question'] for x in items), 'some questions failed to parse'
save('eval_questions_parsed',items)

# ---- check doc state (report honestly, run anyway as the system is) ----
docs=requests.get(f'{BASE}/datasets/{DID}/documents',headers=H,timeout=30).json()
d=docs['data']['docs'][0]
print(f"DOC STATE: run={d['run']} chunk_count={d.get('chunk_count')}")

# ---- create assistant (db-style per SERVICE_CONTRACT.md) ----
HEB=("אתה עוזר שעונה על שאלות לגבי מסמך איפיון. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור במפורש 'לא נמצא מידע במאגר'. אל תמציא מידע.")
body={"name":f"client_eval_{int(time.time())}","dataset_ids":[DID],
  "llm_id":MODEL,"llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,
  "prompt_config":{"system":HEB,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"לא נמצא מידע במאגר","prologue":"שלום!","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,
    "cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
assert r.get('code')==0, r
chat_id=r['data']['id']
print('assistant:',chat_id,'model persisted:',r['data'].get('llm_id'))
save('eval_assistant',r['data'])

# ---- run all 50, fresh session each ----
results=[]
for it in items:
    se=requests.post(f'{BASE}/chats/{chat_id}/sessions',headers=HJ,
        json={"name":f"q{it['n']}"},timeout=30).json()
    sid=se['data']['id']
    t0=time.time()
    try:
        rr=requests.post(f'{BASE}/chats/{chat_id}/completions',headers=HJ,
            json={"question":it['question'],"stream":False,"session_id":sid},timeout=900).json()
    except Exception as e:
        rr={'code':-1,'message':str(e)}
    dt=time.time()-t0
    dd=rr.get('data') or {}
    ans=dd.get('answer','') if isinstance(dd,dict) else ''
    chunks=(dd.get('reference') or {}).get('chunks',[]) if isinstance(dd,dict) else []
    # did reference contain the expected section anchor?
    exp=it['expected_section']
    hit=any(f'[{exp}' in c.get('content','') or f'[{exp}:' in c.get('content','') for c in chunks) if exp else None
    no_info='לא נמצא מידע' in ans or not ans.strip()
    print(f"Q{it['n']:02d} {dt:4.0f}s exp={exp} hit={hit} no_info={no_info} | {ans[:70].replace(chr(10),' ')}")
    results.append({"n":it['n'],"question":it['question'],"expected_section":exp,
                    "seconds":round(dt,1),"ref_hit":hit,"no_info":no_info,
                    "answer":ans,"ref_sections":[ (re.search(r'\[S\d+',c.get('content',''))or[None])[0] if re.search(r'\[S\d+',c.get('content','')) else None for c in chunks],
                    "ref_chunk_count":len(chunks)})
    save('eval_run50_partial',results)

save('eval_run50_results',results)
hits=sum(1 for r in results if r['ref_hit'])
noinfo=sum(1 for r in results if r['no_info'])
print(f"\nSUMMARY: ref_hit={hits}/50  no_info_answers={noinfo}/50")
print('CHAT_ID='+chat_id)
