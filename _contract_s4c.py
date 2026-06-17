import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
DS='2990101865ed11f19d1425719d627201'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

def probe(q,**kw):
    body={"question":q,"dataset_ids":[DS],"page_size":10,"similarity_threshold":0.0,
          "vector_similarity_weight":0.3,**kw}
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=120).json()
    ch=r['data']['chunks']; tot=r['data'].get('total')
    print(f'Q={q!r} kw={kw} -> total={tot} returned={len(ch)}')
    for c in ch[:5]:
        print(f'    sim={c["similarity"]:.3f} vec={c.get("vector_similarity",0):.3f} term={c.get("term_similarity",0):.3f} | {c["content"][:55].replace(chr(10)," ")}')
    return r

# Hebrew question about the chart
r1=probe('באיזה רבעון נרשם שיא המכירות?')
# English equivalent
r2=probe('Which quarter had the peak sales and what was the value?')
# Hebrew with higher vector weight
r3=probe('באיזה רבעון נרשם שיא המכירות?',vector_similarity_weight=0.9)
save('s4_crosslang_hebrew',r1); save('s4_crosslang_english',r2); save('s4_crosslang_hebrew_vec09',r3)
