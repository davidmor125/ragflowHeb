import sys, json, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='c8482642674011f1a56221ba47a3a9e1'
IDX='ragflow_2507563a42bd11f1a6bba9e87ac7a32c'

# find one DONE doc
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
done=[d for d in docs if str(d['run']) in ('DONE','3') and d.get('chunk_count',0)>3]
if not done:
    print('no DONE doc with chunks yet'); sys.exit()
doc=done[0]
DOC=doc['id']
print(f'inspecting: {doc["name"]} | chunk_count={doc["chunk_count"]}')

# chunks via API (parents)
chunks=[];page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1
toks=[len(enc.encode(c['content'])) for c in chunks]
print(f'\nparent chunks via API: {len(chunks)}')
print(f'  token sizes: min={min(toks)} p50={sorted(toks)[len(toks)//2]} max={max(toks)}')
print('  sample content:', chunks[0]['content'][:120].replace(chr(10),' '))

# ES: are there children (parent_child working)?
def es(q):
    cmd=['docker','exec','docker-ragflow-cpu-1','sh','-c',
         f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/{IDX}/_search' -H 'Content-Type: application/json' -d '{q}'"]
    return json.loads(subprocess.run(cmd,capture_output=True).stdout.decode('utf-8','replace'))
tot=es('{"size":0,"query":{"term":{"doc_id":"%s"}}}'%DOC)['hits']['total']['value']
chil=es('{"size":0,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}}}'%DOC)['hits']['total']['value']
print(f'\nES for this doc: total={tot}  children(mom_id)={chil}  parents={tot-chil}')

# child sizes
csmp=es('{"size":200,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}},"_source":["content_with_weight"]}'%DOC)
ctoks=sorted(len(enc.encode(h['_source'].get('content_with_weight',''))) for h in csmp['hits']['hits'])
if ctoks:
    print(f'child sizes: min={ctoks[0]} p50={ctoks[len(ctoks)//2]} max={ctoks[-1]}  | >256:{sum(1 for t in ctoks if t>256)} >2048:{sum(1 for t in ctoks if t>2048)}')
print('\nVERDICT: parent_child=%s, small_chunks=%s, embedding=qwen3' % (chil>0, (max(ctoks)<2200 if ctoks else False)))
