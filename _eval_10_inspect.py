import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
items={x['n']:x for x in json.load(open('_contract_out/eval_questions_parsed.json',encoding='utf-8'))}

# the 2 misses: Q1 (exp S1) and Q8 (exp S16). What got retrieved instead?
for n in [1,8]:
    it=items[n]
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':it['question'],
        'dataset_ids':[DID],'page_size':6,'similarity_threshold':0.0,
        'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
    print('='*80)
    print(f"Q{n} expected={it['expected_section']}: {it['question']}")
    for c in r['data']['chunks']:
        a=re.findall(r'\[S\d+',c['content'])
        print(f"  sim={c['similarity']:.3f} anchors={a[:3]} | {c['content'][:55].replace(chr(10),' ')}")
    # is the expected section present anywhere in retrieval?
    exp=it['expected_section']
    anywhere=any(f'[{exp}' in c['content'] for c in r['data']['chunks'])
    print(f"  -> expected {exp} in retrieval: {anywhere}")
