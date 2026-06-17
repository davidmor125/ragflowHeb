import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

CHAT='e382caaa661b11f1ae84bd00f07a0952'
SID='e38af734661b11f1ae84bd00f07a0952'
HEB_PROMPT=("אתה עוזר ידע מדויק. ענה בעברית בלבד, אך ורק על סמך המידע במאגר הידע שלהלן:\n"
            "{knowledge}\n"
            "אם התשובה אינה נמצאת במאגר — אמור במפורש שאינך יודע. אל תמציא מידע.")

def get_chat():
    r=requests.get(f'{BASE}/chats?id={CHAT}',headers=H,timeout=30).json()
    d=r.get('data')
    if isinstance(d,list): return d[0] if d else None
    if isinstance(d,dict):
        for k in ('chats','items','list'):
            if isinstance(d.get(k),list) and d[k]: return d[k][0]
        return d
    return None

# ---- attempt 1: documented shape via PUT ----
upd={"llm":{"model_name":"gpt-oss:20b@Ollama","temperature":0.1},
     "prompt":{"similarity_threshold":0.2,"top_n":8,"prompt":HEB_PROMPT,
               "variables":[{"key":"knowledge","optional":False}]}}
save('s5_chat_update_request',upd)
r=requests.put(f'{BASE}/chats/{CHAT}',headers=HJ,json=upd,timeout=30).json()
print('PUT documented shape -> code:',r.get('code'),'|',str(r.get('message'))[:200])
c=get_chat()
print('  llm_id now:',c.get('llm_id'))
print('  system prompt now Hebrew:',('עברית' in (c.get('prompt_config') or {}).get('system','')))
print('  top_n:',c.get('top_n'),'sim_th:',c.get('similarity_threshold'))
applied = c.get('llm_id')=='gpt-oss:20b@Ollama' and 'עברית' in (c.get('prompt_config') or {}).get('system','')

# ---- attempt 2: db-style fields if needed ----
if not applied:
    upd2={"llm_id":"gpt-oss:20b@Ollama",
          "llm_setting":{"temperature":0.1},
          "similarity_threshold":0.2,"top_n":8,
          "prompt_config":{"system":HEB_PROMPT,
                           "parameters":[{"key":"knowledge","optional":False}],
                           "empty_response":"","prologue":"שלום! איך אפשר לעזור?",
                           "quote":True,"refine_multiturn":False,"tts":False}}
    save('s5_chat_update_request_dbstyle',upd2)
    r=requests.put(f'{BASE}/chats/{CHAT}',headers=HJ,json=upd2,timeout=30).json()
    print('PUT db-style shape -> code:',r.get('code'),'|',str(r.get('message'))[:200])
    c=get_chat()
    print('  llm_id now:',c.get('llm_id'))
    print('  system Hebrew:','עברית' in (c.get('prompt_config') or {}).get('system',''))
    print('  top_n:',c.get('top_n'),'sim_th:',c.get('similarity_threshold'))

save('s5_chat_after_update',c)

# ---- verify in a live completion: prompt actually used + model ----
q='מהו זמן התגובה הממוצע של המערכת לפי טבלת המפרט?'
t0=time.time()
r=requests.post(f'{BASE}/chats/{CHAT}/completions',headers=HJ,
    json={"question":q,"stream":False,"session_id":SID},timeout=600).json()
dt=time.time()-t0
save('s5_completion_after_update',r)
d=r.get('data') or {}
ans=d.get('answer','')
used_prompt=d.get('prompt','')
print(f'completion {dt:.1f}s | answer: {ans[:150]}')
print('  prompt used is Hebrew custom:','עוזר ידע מדויק' in used_prompt)
print('  answer has 850:','850' in ans)
