import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
DS='2990101865ed11f19d1425719d627201'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

q='באיזה רבעון נרשם שיא המכירות?'
body={"question":q,"dataset_ids":[DS],"page_size":10,"similarity_threshold":0.0,
      "vector_similarity_weight":0.3,"cross_languages":["English"]}
t0=time.time()
r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()
dt=time.time()-t0
save('s4_crosslang_enabled',r)
ch=r['data']['chunks']
print(f'cross_languages=["English"] {dt:.1f}s -> total={r["data"].get("total")} returned={len(ch)}')
for c in ch[:5]:
    print(f'  sim={c["similarity"]:.3f} vec={c.get("vector_similarity",0):.3f} | {c["content"][:60].replace(chr(10)," ")}')
chart=[i for i,c in enumerate(ch) if '260' in c['content'] and 'Q4' in c['content']]
print('chart chunk rank:',chart[0] if chart else -1)
