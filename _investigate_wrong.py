import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'

d=json.load(open('_contract_out/hozrim132j_partial.json',encoding='utf-8'))
wrongs=[x for x in d if x['verdict']=='wrong']
print(f'{len(wrongs)} wrong answers — investigating each\n')

for x in wrongs:
    print('='*90)
    print(f"Q{x['n']} [{x['topic']} / נוהל {x['procedure']}]")
    print(f"  question: {x['question']}")
    print(f"  judge reason: {x['reason']}")
    # re-run retrieval to see WHAT was retrieved + whether the right procedure file is there
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json={
        'question':x['question'],'dataset_ids':[DID],'page_size':6,'similarity_threshold':0.0,
        'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
        'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=300).json()
    ch=r.get('data',{}).get('chunks',[])
    proc=str(x['procedure'])
    print(f"  retrieved {len(ch)} chunks. Source docs:")
    for c in ch[:6]:
        dn=c.get('document_name','')
        has_proc = proc in dn or proc in c.get('content','')
        print(f"    sim={c.get('similarity',0):.3f} doc={dn} {'<-- EXPECTED PROC' if has_proc else ''}")
    found=any(proc in c.get('document_name','') for c in ch)
    print(f"  >> expected procedure {proc} in retrieved docs: {found}")
    print(f"  ANSWER: {x['answer'][:140]}".replace(chr(10),' '))
    print(f"  EXPECTED: {x['expected_answer'][:140]}".replace(chr(10),' '))
    print()
