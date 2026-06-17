import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'; os.makedirs(OUT,exist_ok=True)
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'   # parsed dataset from S1-S2
TS=str(int(time.time()))
MODEL='gpt-oss:20b@Ollama'              # local model (cloud models hit weekly quota)

# ---- 5.1a negative probe: prompt WITHOUT {knowledge} ----
bad={"name":f"contract_noknow_{TS}","dataset_ids":[DS],
     "llm":{"model_name":MODEL},
     "prompt":{"prompt":"ענה בעברית בלבד על סמך המסמכים."}}
r=requests.post(f'{BASE}/chats',headers=HJ,json=bad,timeout=30).json()
save('s5_chat_create_no_knowledge',r)
print('A) create WITHOUT {knowledge}: code=',r.get('code'),'|',str(r.get('message'))[:150])
bad_id=r.get('data',{}).get('id') if isinstance(r.get('data'),dict) else None

# ---- 5.1b proper assistant: Hebrew system prompt WITH {knowledge} ----
body={"name":f"contract_chat_{TS}","dataset_ids":[DS],
  "llm":{"model_name":MODEL,"temperature":0.1,"top_p":0.3,
         "presence_penalty":0.4,"frequency_penalty":0.7},
  "prompt":{"similarity_threshold":0.2,"keywords_similarity_weight":0.7,"top_n":8,
    "show_quote":True,
    "variables":[{"key":"knowledge","optional":False}],
    "prompt":("אתה עוזר ידע מדויק. ענה בעברית בלבד, אך ורק על סמך המידע במאגר הידע שלהלן:\n"
              "{knowledge}\n"
              "אם התשובה אינה נמצאת במאגר — אמור במפורש שאינך יודע. אל תמציא מידע.")}}
save('s5_chat_create_request',body)
r=requests.post(f'{BASE}/chats',headers=HJ,json=body,timeout=30).json()
save('s5_chat_create_response',r)
if r.get('code')!=0:
    print('FATAL create chat:',r); sys.exit(1)
chat_id=r['data']['id']
print('B) chat created:',chat_id)

# ---- 5.2 session ----
se=requests.post(f'{BASE}/chats/{chat_id}/sessions',headers=HJ,json={"name":f"contract_session_{TS}"},timeout=30).json()
save('s5_session_response',se)
sid=se['data']['id']
print('C) session:',sid)

# ---- 5.3 completion stream=false ----
q1='מהו המזהה המופיע בשורת הכותרת הראשית של מסמך הבדיקה (בסוגריים מרובעים)?'
req={"question":q1,"stream":False,"session_id":sid}
save('s5_completion_request',req)
t0=time.time()
r=requests.post(f'{BASE}/chats/{chat_id}/completions',headers=HJ,json=req,timeout=600).json()
dt=time.time()-t0
save('s5_completion_response',r)
if r.get('code')!=0:
    print('FATAL completion:',r); sys.exit(1)
data=r['data']; ans=data.get('answer',''); ref=data.get('reference',{}) or {}
print(f'D) non-stream answer in {dt:.1f}s: {ans[:200]}')
print('   data keys:',sorted(data.keys()))
print('   reference keys:',sorted(ref.keys()))
chunks=ref.get('chunks',[])
print('   ref chunks:',len(chunks))
if chunks:
    print('   chunk[0] keys:',sorted(chunks[0].keys()))
    schema={k:type(v).__name__ for k,v in chunks[0].items()}
    save('s5_reference_chunk_schema',schema)
print('   doc_aggs:',json.dumps(ref.get('doc_aggs'),ensure_ascii=False)[:300])
anchor='[כותרת-ראשית: מסמך-בדיקה-12345]'
anchor_ok=any(anchor in c.get('content','') for c in chunks)
print('   ANCHOR VERBATIM IN REF CONTENT:',anchor_ok)
heb=any('֐'<=ch<='ת' for ch in ans)
print('   HEBREW ANSWER:',heb)
print('   answer mentions 12345:','12345' in ans)

# ---- 5.4 completion stream=true ----
q2='אילו שפות נתמכות במערכת לפי המסמך?'
req2={"question":q2,"stream":True,"session_id":sid}
events=[]
t0=time.time(); first_tok=None
with requests.post(f'{BASE}/chats/{chat_id}/completions',headers=HJ,json=req2,stream=True,timeout=600) as resp:
    print('E) stream HTTP status:',resp.status_code,'content-type:',resp.headers.get('content-type'))
    for line in resp.iter_lines(decode_unicode=True):
        if line:
            if first_tok is None: first_tok=time.time()-t0
            events.append(line)
dt2=time.time()-t0
save('s5_completion_stream_sample',{'http_content_type':resp.headers.get('content-type'),
    'event_count':len(events),'first_token_s':round(first_tok or -1,2),'total_s':round(dt2,1),
    'first_2_events':events[:2],'last_2_events':events[-2:]})
print(f'   stream: {len(events)} events, first token {first_tok:.1f}s, total {dt2:.1f}s')
# parse final event (the one carrying full answer+reference)
final=None
for ev in reversed(events):
    s=ev[5:] if ev.startswith('data:') else ev
    try:
        j=json.loads(s)
        if isinstance(j.get('data'),dict) and j['data'].get('reference'):
            final=j; break
    except Exception: pass
if final:
    fans=final['data'].get('answer','')
    print('   final stream answer:',fans[:150])
    print('   final has reference.chunks:',len(final['data']['reference'].get('chunks',[])))
    save('s5_completion_stream_final_event',final)

# cleanup the bad probe assistant if it was created
if bad_id:
    requests.delete(f'{BASE}/chats',headers=HJ,json={'ids':[bad_id]},timeout=30)

print('CHAT_ID='+chat_id)
print('SESSION_ID='+sid)
