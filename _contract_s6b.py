import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
DS='2990101865ed11f19d1425719d627201'

def probe(q,**kw):
    body={"question":q,"dataset_ids":[DS],"page_size":10,"similarity_threshold":0.0,
          "vector_similarity_weight":0.3,**kw}
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()
    ch=r['data']['chunks']
    print(f'Q={q!r} {kw} -> {len(ch)} chunks')
    for c in ch[:6]:
        mark=''
        if 'ZX9871' in c['content']: mark=' <<TABLE'
        if 'MERMAIDKEY42' in c['content']: mark=' <<MERMAID'
        print(f'  sim={c["similarity"]:.3f} vec={c.get("vector_similarity",0):.3f} term={c.get("term_similarity",0):.3f}{mark} | {c["content"][:50].replace(chr(10)," ")}')

probe('מהו הקוד הסודי המופיע בטבלת המפרט הטכני?')
probe('איזה מפתח מופיע בתרשים הזרימה בשלב ניסוח התשובה?')
probe('הקוד הסודי בטבלה')
probe('MERMAIDKEY42')
