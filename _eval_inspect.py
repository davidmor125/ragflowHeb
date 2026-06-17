import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
enc=tiktoken.get_encoding('cl100k_base')
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

docs=requests.get(f'{BASE}/datasets/{DID}/documents?id={DOC}',headers=H,timeout=30).json()
d=docs['data']['docs'][0]
print('doc:',d['name'],'run=',d['run'],'progress=',d.get('progress'),'chunk_count=',d.get('chunk_count'))
print('parser_config:',json.dumps(d.get('parser_config',{}),ensure_ascii=False)[:400])
print('progress_msg tail:',(d.get('progress_msg','') or '')[-400:])

# fetch all chunks
chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1
print('chunks fetched:',len(chunks))

# Analyze [S#] anchor distribution
anchor_re=re.compile(r'\[S(\d+)\]')
chunks_with_anchor=0
all_anchors=[]
toks=[]
body_without_header=[]  # heuristic: substantial body text but no [S#] token at all
for i,c in enumerate(chunks):
    content=c['content']
    toks.append(len(enc.encode(content)))
    anchors=anchor_re.findall(content)
    if anchors:
        chunks_with_anchor+=1
        all_anchors.extend(anchors)
    else:
        # body with no anchor — only flag if it has real content (not just a stub)
        if len(content.strip())>80:
            body_without_header.append((i,len(content),content[:90].replace('\n',' ')))

# did the previously-failing S21 and the table/diagram sections make it in?
for probe in ['[S21','[S28','[S5]','[S44','[S71']:
    present=any(probe in c['content'] for c in chunks)
    print(f'   probe {probe!r} present in some chunk: {present}')

print(f'\nchunks with >=1 [S#] anchor: {chunks_with_anchor}/{len(chunks)}')
print(f'distinct sections referenced: {len(set(all_anchors))}')
print(f'token dist: min={min(toks)} median={sorted(toks)[len(toks)//2]} max={max(toks)}')
print(f'\nBODY-WITHOUT-ANCHOR chunks (>80 chars, no [S#]): {len(body_without_header)}')
for i,ln,prev in body_without_header[:25]:
    print(f'   chunk[{i}] {ln}ch: {prev}')

# Which sections appear multiple times split across chunks?
from collections import Counter
cnt=Counter(all_anchors)
multi=[(s,n) for s,n in cnt.items() if n>1]
print(f'\nsections spanning multiple chunks (anchor repeated): {len(multi)}')
print('  sample:',sorted(multi,key=lambda x:-x[1])[:10])

save('eval_chunk_inspect',{'chunk_count':len(chunks),'with_anchor':chunks_with_anchor,
    'distinct_sections':len(set(all_anchors)),'token_min':min(toks),'token_med':sorted(toks)[len(toks)//2],
    'token_max':max(toks),'body_without_anchor':len(body_without_header),
    'body_without_anchor_samples':[{'idx':i,'len':l,'preview':p} for i,l,p in body_without_header[:30]],
    'multi_chunk_sections':sorted(multi,key=lambda x:-x[1])[:30]})
