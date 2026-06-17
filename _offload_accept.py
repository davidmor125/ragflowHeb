import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken, re
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
enc=tiktoken.get_encoding('cl100k_base')   # same encoder as the service

RUN_TAG=sys.argv[1] if len(sys.argv)>1 else 'r1'
FIX='_client_spec_fixture.md'

# source-of-truth anchors
src=open(FIX,encoding='utf-8').read()
src_anchors=set(re.findall(r'\[S\d+:[^\]]*\]',src))
print(f'fixture: {len(src)} chars, {len(src_anchors)} unique [S#:] anchors')

# 1. dataset with the client's exact config
ds_body={"name":f"client_offload_{RUN_TAG}_{int(time.time())}",
  "embedding_model":"bge-m3@Ollama","chunk_method":"naive",
  "parser_config":{"chunk_token_num":1024,"delimiter":"\\n!?;。;！？",
    "layout_recognize":"DeepDOC","auto_keywords":3,"auto_questions":2,
    "raptor":{"use_raptor":False},"graphrag":{"use_graphrag":False}}}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json=ds_body,timeout=30).json()
assert ds.get('code')==0, ds
did=ds['data']['id']
save(f'offload_{RUN_TAG}_dataset',ds)
print('dataset:',did)

def run_once(tag):
    t0=time.time()
    with open(FIX,'rb') as fh:
        up=requests.post(f'{BASE}/datasets/{did}/documents',headers=H,
            files={'file':('client_spec.md',fh)},timeout=120).json()
    assert up.get('code')==0, up
    docid=up['data'][0]['id']
    pr=requests.post(f'{BASE}/datasets/{did}/chunks',headers=HJ,json={'document_ids':[docid]},timeout=30).json()
    assert pr.get('code')==0, pr
    last=None; d=None
    while time.time()-t0<2400:
        docs=requests.get(f'{BASE}/datasets/{did}/documents?id={docid}',headers=H,timeout=30).json()
        d=docs['data']['docs'][0]
        run,prog=str(d['run']),round(d.get('progress',0),2)
        if (run,prog)!=last:
            print(f'  [{tag}][{int(time.time()-t0):4d}s] run={run} progress={prog} chunks={d.get("chunk_count",0)}')
            last=(run,prog)
        if run in ('3','DONE') and d.get('progress',0)>=1: break
        if run in ('4','FAIL'):
            print(f'[{tag}] PARSE FAILED:',d.get('progress_msg','')[-600:])
            save(f'offload_{RUN_TAG}_{tag}_doc_FAIL',d)
            sys.exit(1)
        time.sleep(8)
    wall=time.time()-t0
    save(f'offload_{RUN_TAG}_{tag}_doc_final',d)
    print(f'[{tag}] DONE: wall={wall:.0f}s server={d.get("process_duration")}s chunks={d.get("chunk_count")}')
    return docid,d,wall

def verify(docid,tag):
    chunks=[]; page=1
    while True:
        ch=requests.get(f'{BASE}/datasets/{did}/documents/{docid}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
        cs=ch['data']['chunks']
        if not cs: break
        chunks.extend(cs); page+=1
    toks=[len(enc.encode(c['content'])) for c in chunks]
    allc='\n'.join(c['content'] for c in chunks)
    found=set(a for a in src_anchors if a in allc)
    over=[t for t in toks if t>1024+64]   # small tolerance for added context
    kw=sum(1 for c in chunks if c.get('important_keywords'))
    qs=sum(1 for c in chunks if c.get('questions'))
    print(f'[{tag}] chunks={len(chunks)} max_tokens={max(toks)} median={sorted(toks)[len(toks)//2]} over_cap={len(over)}')
    print(f'[{tag}] anchors survived: {len(found)}/{len(src_anchors)}')
    print(f'[{tag}] enrichment: keywords on {kw}/{len(chunks)}, questions on {qs}/{len(chunks)}')
    save(f'offload_{RUN_TAG}_{tag}_verify',{'chunks':len(chunks),'max_tokens':max(toks),
        'token_dist':{'p50':sorted(toks)[len(toks)//2],'p90':sorted(toks)[int(len(toks)*0.9)],'max':max(toks)},
        'over_cap_count':len(over),'over_cap_values':sorted(over,reverse=True)[:10],
        'anchors_total':len(src_anchors),'anchors_found':len(found),
        'anchors_missing':sorted(src_anchors-found)[:10],
        'keywords_chunks':kw,'questions_chunks':qs})
    return len(over)==0 and len(found)==len(src_anchors)

# run 1
docid,d,w1=run_once('run1')
ok1=verify(docid,'run1')

# stability: delete the document, upload + parse again
r=requests.delete(f'{BASE}/datasets/{did}/documents',headers=HJ,json={'ids':[docid]},timeout=60).json()
print('delete doc for rerun:',r.get('code'))
docid2,d2,w2=run_once('run2')
ok2=verify(docid2,'run2')

print(f'RESULT: run1_ok={ok1} run2_ok={ok2} walls=({w1:.0f}s,{w2:.0f}s)')
print('DATASET='+did)
