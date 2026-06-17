import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='3db1df6c669d11f1b9e5df329cd4ee1f'

items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
PARTIALS=[4,10,12,13,16,20,24,29,39,44,46,47]

BASE_PROMPT=("אתה עוזר שעונה על שאלות לגבי מסמך איפיון. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור במפורש 'לא נמצא מידע במאגר'. אל תמציא מידע.")
# Variant B prompt adds table-fidelity + anti-leakage instructions
TABLE_PROMPT=("אתה עוזר שעונה על שאלות לגבי מסמך איפיון. ענה בעברית בלבד, אך ורק על סמך "
     "המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "כללים: (1) ענה אך ורק על הפרק שהשאלה שואלת עליו — אל תוסיף מידע מפרקים אחרים "
     "גם אם הוא מופיע במאגר. (2) כשהמקור הוא טבלה — שחזר את כל השורות והעמודות "
     "במלואן, אל תסכם ואל תשמיט. (3) אם התשובה אינה נמצאת — אמור 'לא נמצא מידע במאגר'.")

def make_assistant(name,model,top_n,prompt):
    body={"name":name,"dataset_ids":[DID],"llm_id":model,"llm_setting":{"temperature":0.1},
      "similarity_threshold":0.1,"top_n":top_n,
      "prompt_config":{"system":prompt,"parameters":[{"key":"knowledge","optional":False}],
        "empty_response":"לא נמצא מידע במאגר","prologue":"שלום!","quote":True,
        "refine_multiturn":False,"tts":False,"keyword":True,
        "cross_languages":["Hebrew","English"]}}
    r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
    assert r.get('code')==0, r
    return r['data']['id'],r['data']

def ask(chat_id,q):
    se=requests.post(f'{BASE}/chats/{chat_id}/sessions',headers=HJ,json={"name":"x"},timeout=30).json()
    sid=se['data']['id']
    t0=time.time()
    rr=requests.post(f'{BASE}/chats/{chat_id}/completions',headers=HJ,
        json={"question":q,"stream":False,"session_id":sid},timeout=900).json()
    dt=time.time()-t0
    dd=rr.get('data') or {}
    ans=dd.get('answer','') if isinstance(dd,dict) else ''
    chunks=(dd.get('reference') or {}).get('chunks',[]) if isinstance(dd,dict) else []
    return ans,chunks,dt

variant=sys.argv[1] if len(sys.argv)>1 else 'A'
ts=str(int(time.time()))
CONF={
 'A':('gpt-oss:20b@Ollama',3,BASE_PROMPT,'top_n=3, gpt-oss:20b, base prompt'),
 'B':('gpt-oss:120b-cloud@Ollama',3,TABLE_PROMPT,'top_n=3, gpt-oss:120b-cloud, table prompt'),
 'C':('gemma4:26b@Ollama',3,TABLE_PROMPT,'top_n=3, gemma4:26b (local), table prompt'),
 'D':('gpt-oss:120b@Ollama',3,TABLE_PROMPT,'top_n=3, gpt-oss:120b (LOCAL), table prompt'),
 'E':('gemma4:31b-cloud@Ollama',3,TABLE_PROMPT,'top_n=3, gemma4:31b-cloud (org model), table prompt'),
}
model,topn,prompt,desc=CONF[variant]
cid,meta=make_assistant(f'part{variant}_{ts}',model,topn,prompt)
print(f'Variant {variant}: {desc} — chat {cid}')
print('persisted llm:',meta.get('llm_id'),'top_n:',meta.get('top_n'))

out=[]
for n in PARTIALS:
    it=items[n]
    ans,chunks,dt=ask(cid,it['question'])
    exp=it['expected_section']
    hit=any(f'[{exp}' in c.get('content','') for c in chunks)
    print(f"Q{n:02d} exp={exp} hit={hit} {dt:4.0f}s | {ans[:70].replace(chr(10),' ')}")
    out.append({"n":n,"question":it['question'],"expected_section":exp,
                "ref_hit":hit,"answer":ans,"seconds":round(dt,1),
                "ref_count":len(chunks)})
    save(f'eval_partials_variant{variant}_partial',out)
save(f'eval_partials_variant{variant}',out)
print(f'\nVariant {variant} done.')
