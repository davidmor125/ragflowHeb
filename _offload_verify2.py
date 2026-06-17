import sys, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
enc=tiktoken.get_encoding('cl100k_base')
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DID='c9aecda0668d11f1b9e5df329cd4ee1f'
src=open('_client_spec_fixture.md',encoding='utf-8').read()
src_anchors=set(re.findall(r'\[S\d+:[^\]]*\]',src))

docs=requests.get(f'{BASE}/datasets/{DID}/documents?page_size=10',headers=H,timeout=30).json()
doc=docs['data']['docs'][0]
docid=doc['id']
print('doc:',doc['name'],'run=',doc['run'],'chunk_count=',doc['chunk_count'])

chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{docid}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1
toks=[len(enc.encode(c['content'])) for c in chunks]
allc='\n'.join(c['content'] for c in chunks)
found=set(a for a in src_anchors if a in allc)
over=[t for t in toks if t>1024+64]
print(f'chunks fetched={len(chunks)} max_tokens={max(toks)} median={sorted(toks)[len(toks)//2]} over_cap={len(over)}')
print(f'anchors survived: {len(found)}/{len(src_anchors)}')
save('offload_r1_run2_verify_late',{'chunks':len(chunks),'max_tokens':max(toks),
    'over_cap_count':len(over),'anchors_total':len(src_anchors),'anchors_found':len(found),
    'doc_chunk_count':doc['chunk_count'],'note':'re-verification minutes after DONE (first verify raced ES refresh)'})
