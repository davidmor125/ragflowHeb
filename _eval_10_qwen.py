import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='0438ba6466fa11f1a56021ba47a3a9e1'   # Qwen3 dataset

items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
PICK=[1,3,8,20,21,24,29,31,44,46]
label={1:'text',3:'text',8:'text(was miss)',20:'TABLE S44',21:'TABLE S46',
       24:'TABLE S53',29:'TABLE S66',31:'TABLE S71',44:'TABLE S102',46:'TABLE S107'}

# SAME setup as bge-m3 run: gemma4:31b-cloud, top_n=3, table-fidelity prompt
PROMPT=("אתה עוזר שעונה על שאלות לגבי מסמך איפיון. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "כללים: ענה רק על הפרק שנשאל; כשהמקור טבלה — שחזר כל שורה; אם אין מידע — 'לא נמצא מידע במאגר'.")
body={"name":f"eval10qwenRR_{int(time.time())}","dataset_ids":[DID],
  "llm_id":"gemma4:31b-cloud@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.1,"top_n":8,"rerank_id":"Qwen3-Reranker-4B@HuggingFace",
  "prompt_config":{"system":PROMPT,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"לא נמצא מידע במאגר","prologue":"שלום","quote":True,
    "refine_multiturn":False,"tts":False,"keyword":True,"cross_languages":["Hebrew","English"]}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
assert r.get('code')==0, r
cid=r['data']['id']
print('assistant:',cid,'(QWEN3 dataset, gemma4:31b-cloud, top_n=3)\n')

out=[]
for n in PICK:
    it=items[n]
    se=requests.post(f'{BASE}/chats/{cid}/sessions',headers=HJ,json={"name":f"q{n}"},timeout=30).json()
    sid=se['data']['id']
    t0=time.time()
    rr=requests.post(f'{BASE}/chats/{cid}/completions',headers=HJ,
        json={"question":it['question'],"stream":False,"session_id":sid},timeout=900).json()
    dt=time.time()-t0
    dd=rr.get('data') or {}
    ans=dd.get('answer','') if isinstance(dd,dict) else ''
    chunks=(dd.get('reference') or {}).get('chunks',[]) if isinstance(dd,dict) else []
    exp=it['expected_section']
    hit=any(f'[{exp}' in c.get('content','') for c in chunks)
    print(f"Q{n:02d} [{label[n]:15s}] exp={exp} hit={hit} {dt:4.0f}s | {ans[:55].replace(chr(10),' ')}")
    out.append({"n":n,"label":label[n],"question":it['question'],"expected_section":exp,
                "ref_hit":hit,"answer":ans,"seconds":round(dt,1)})
    save('eval_10qwen_partial',out)
save('eval_10qwen',out)
hits=sum(1 for x in out if x['ref_hit'])
print(f'\nref_hit: {hits}/10')
