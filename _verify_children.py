import sys, json, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='da97676866f011f1b9e5df329cd4ee1f'
IDX='ragflow_2507563a42bd11f1a6bba9e87ac7a32c'

def es(q):
    cmd=['docker','exec','docker-ragflow-cpu-1','sh','-c',
         f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/{IDX}/_search' -H 'Content-Type: application/json' -d '{q}'"]
    out=subprocess.run(cmd,capture_output=True)
    return json.loads(out.stdout.decode('utf-8','replace'))

# 1. count parents vs children in ES
print('=== ES: parent vs child split ===')
tot=es('{"size":0,"query":{"term":{"doc_id":"%s"}}}'%DOC)
print('  total ES docs for file:',tot['hits']['total']['value'])
child=es('{"size":0,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}}}'%DOC)
print('  CHILDREN (have mom_id):',child['hits']['total']['value'])
avail=es('{"size":0,"query":{"term":{"doc_id":"%s"}},"aggs":{"a":{"terms":{"field":"available_int"}}}}'%DOC)
for b in avail.get('aggregations',{}).get('a',{}).get('buckets',[]):
    print(f'    available_int={b["key"]}: {b["doc_count"]} (0=parent/reference, 1=searchable child)')

# 2. sample children: size + does each carry [S#]?
print('\n=== sample CHILDREN: size + title retention ===')
sample=es('{"size":12,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}},"_source":["content_with_weight","mom_id"]}'%DOC)
child_toks=[]; with_anchor=0; total=0
for h in sample['hits']['hits']:
    c=h['_source'].get('content_with_weight','')
    t=len(enc.encode(c)); child_toks.append(t)
    has=bool(re.search(r'\[S\d+',c))
    total+=1; with_anchor+=has
    print(f'  child tok={t:4d} has[S#]={has} mom={h["_source"].get("mom_id","")[:12]} | {c[:50].replace(chr(10)," ")}')

# 3. broader child size distribution
allch=es('{"size":600,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}},"_source":["content_with_weight"]}'%DOC)
toks=sorted(len(enc.encode(h['_source'].get('content_with_weight',''))) for h in allch['hits']['hits'])
if toks:
    print(f'\n=== CHILD size distribution ({len(toks)} children) ===')
    print(f'  min={toks[0]} p50={toks[len(toks)//2]} p90={toks[int(len(toks)*0.9)]} max={toks[-1]}')
    print(f'  children over 512 tok: {sum(1 for t in toks if t>512)}')
    print(f'  children over 2048 tok (vector-truncation risk): {sum(1 for t in toks if t>2048)}')

# 4. what does retrieval return now? (should be parent content for citation)
print('\n=== retrieval granularity now ===')
q='מהם השלבים האפשריים של סטטוס הזמנה במערכת?'
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
    'page_size':5,'similarity_threshold':0.0,'vector_similarity_weight':0.3,
    'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
for c in r['data']['chunks'][:5]:
    t=len(enc.encode(c['content'])); a=re.findall(r'\[S\d+',c['content'])
    print(f'  sim={c["similarity"]:.3f} tok={t} anchors={a[:2]} | {c["content"][:45].replace(chr(10)," ")}')
