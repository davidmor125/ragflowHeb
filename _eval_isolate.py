import sys, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
DID='3db1df6c669d11f1b9e5df329cd4ee1f'

# For the failing/partial Qs, check the RAW retrieval: did the correct section's
# FULL content (table rows / flowchart) actually come back? This isolates
# retrieval/chunk quality from answer-generation quality.
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
check={8:'S16',26:'S59',42:'S97',50:'S116',20:'S44',46:'S107',102:None}
for n,exp in check.items():
    if n not in items: continue
    it=items[n]
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json={
        'question':it['question'],'dataset_ids':[DID],'page_size':8,
        'similarity_threshold':0.0,'vector_similarity_weight':0.3,
        'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
    ch=r['data']['chunks']
    secs=[ (re.search(r'\[S\d+',c['content'])or[''])[0] for c in ch]
    # find the chunk that contains the expected section, show how complete it is
    expnum=it['expected_section']
    hit=[c for c in ch if expnum and f'[{expnum}' in c['content']]
    print(f"Q{n} exp={expnum} retrieved_secs={secs}")
    if hit:
        c=hit[0]
        print(f"   FULL expected-section chunk ({len(c['content'])} chars):")
        print('   '+c['content'][:500].replace('\n',' '))
    else:
        print(f"   *** expected section {expnum} NOT in retrieval ***")
    print()
