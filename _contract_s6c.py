import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
HJ={'Authorization':f'Bearer {KEY}','Content-Type':'application/json'}
DS='2990101865ed11f19d1425719d627201'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

res={}
for tag,q in [('q2','מהו הקוד הסודי המופיע בטבלת המפרט הטכני?'),
              ('q3','איזה מפתח מופיע בתרשים הזרימה בשלב ניסוח התשובה?')]:
    r=requests.post(f'{BASE}/retrieval',headers=HJ,
        json={'question':q,'dataset_ids':[DS],'page_size':10,'similarity_threshold':0.0,
              'vector_similarity_weight':0.3,'keyword':True},timeout=300).json()
    ch=r['data']['chunks']
    print(q[:35],'->',len(ch),'chunks (keyword=True)')
    for c in ch[:5]:
        m=' <<TABLE' if 'ZX9871' in c['content'] else (' <<MERMAID' if 'MERMAIDKEY42' in c['content'] else '')
        print(f"  sim={c['similarity']:.3f}{m} | {c['content'][:50]}".replace(chr(10),' '))
    res[tag]=r
save('s6_retrieval_keyword_true',{k:v['data'] for k,v in res.items()})
