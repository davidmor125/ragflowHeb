import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

# --- chunks via the documents API (what this returns) ---
chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1
toks=[len(enc.encode(c['content'])) for c in chunks]
print(f'=== chunks via documents API: {len(chunks)} ===')
print(f'token dist: min={min(toks)} p50={sorted(toks)[len(toks)//2]} max={max(toks)}')
over=[t for t in toks if t>512]
print(f'chunks over 512 tok: {len(over)} -> {sorted(over,reverse=True)[:8]}')

# --- what does RETRIEVAL actually return? children or parents? ---
# Run a retrieval and inspect the granularity + whether parent content comes back
print('\n=== RETRIEVAL granularity test ===')
q='מהם השלבים האפשריים של סטטוס הזמנה במערכת?'
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={
    'question':q,'dataset_ids':[DID],'page_size':8,'similarity_threshold':0.0,
    'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
rc=r['data']['chunks']
print(f'retrieval returned {len(rc)} chunks, total candidates={r["data"].get("total")}')
for c in rc[:5]:
    t=len(enc.encode(c['content']))
    anchors=re.findall(r'\[S\d+',c['content'])
    print(f'  sim={c["similarity"]:.3f} tok={t} anchors={anchors[:3]} | {c["content"][:55].replace(chr(10)," ")}')

# --- ES direct: count children (available_int=0) vs parents to PROVE children exist ---
print('\n=== Direct ES check: parent vs child counts ===')
import subprocess
# query ES inside the container for this doc: total docs, and how many have mom_id
es_q='{"size":0,"query":{"term":{"doc_id":"%s"}},"aggs":{"by_avail":{"terms":{"field":"available_int"}}}}'%DOC
cmd=['docker','exec','docker-ragflow-cpu-1','sh','-c',
     f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/ragflow_2507563a42bd11f1a6bba9e87ac7a32c/_search' -H 'Content-Type: application/json' -d '{es_q}'"]
out=subprocess.run(cmd,capture_output=True,text=True)
try:
    j=json.loads(out.stdout)
    print('  total docs in ES for this file:',j['hits']['total']['value'])
    for b in j.get('aggregations',{}).get('by_avail',{}).get('buckets',[]):
        label='child(available=0)' if b['key']==0 else f'available={b["key"]}'
        print(f'    {label}: {b["doc_count"]}')
except Exception as e:
    print('  ES parse fail:',out.stdout[:300],out.stderr[:200])

# also check mom_id presence
es_q2='{"size":0,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}}}'%DOC
cmd2=['docker','exec','docker-ragflow-cpu-1','sh','-c',
     f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/ragflow_2507563a42bd11f1a6bba9e87ac7a32c/_search' -H 'Content-Type: application/json' -d '{es_q2}'"]
out2=subprocess.run(cmd2,capture_output=True,text=True)
try:
    j2=json.loads(out2.stdout)
    print('  docs WITH mom_id (children):',j2['hits']['total']['value'])
except Exception as e:
    print('  mom_id check fail:',out2.stdout[:200])
