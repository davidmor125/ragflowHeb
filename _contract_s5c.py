import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'
TS=str(int(time.time()))
HEB=("אתה עוזר ידע מדויק. ענה בעברית בלבד, אך ורק על סמך המידע במאגר הידע שלהלן:\n{knowledge}\n"
     "אם התשובה אינה נמצאת במאגר — אמור במפורש שאינך יודע.")

body={"name":f"contract_dbstyle_{TS}","dataset_ids":[DS],
  "llm_id":"gpt-oss:20b@Ollama","llm_setting":{"temperature":0.1},
  "similarity_threshold":0.2,"top_n":8,
  "prompt_config":{"system":HEB,"parameters":[{"key":"knowledge","optional":False}],
    "empty_response":"","prologue":"שלום!","quote":True,"refine_multiturn":False,"tts":False}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
save('s5_chat_create_dbstyle_response',r)
d=r.get('data') or {}
print('POST db-style: code=',r.get('code'))
print('  persisted llm_id:',d.get('llm_id'))
print('  persisted system Hebrew:','עוזר ידע מדויק' in (d.get('prompt_config') or {}).get('system',''))
print('  top_n:',d.get('top_n'),'sim_th:',d.get('similarity_threshold'))
# cleanup probe
if d.get('id'):
    dr=requests.delete(f'{BASE}/chats',headers=HJ,json={'ids':[d['id']]},timeout=30).json()
    print('  cleanup delete code:',dr.get('code'))
