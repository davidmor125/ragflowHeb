import sys, json, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='0438ba6466fa11f1a56021ba47a3a9e1'   # Qwen dataset
DOC='04456cb466fa11f1a56021ba47a3a9e1'
IDX='ragflow_2507563a42bd11f1a6bba9e87ac7a32c'

# dataset config
ds=requests.get(f'{BASE}/datasets?id={DID}',headers=H,timeout=30).json()
d=ds['data'][0] if isinstance(ds['data'],list) else ds['data']
pc=d.get('parser_config',{})
print('Qwen dataset config:')
print('  chunk_token_num =',pc.get('chunk_token_num'))
print('  use_parent_child =',pc.get('parent_child',{}).get('use_parent_child'))
print('  embedding =',d.get('embedding_model'),'| total chunk_count =',d.get('chunk_count'))

# ES: parent vs child + size distribution
def es(q):
    cmd=['docker','exec','docker-ragflow-cpu-1','sh','-c',
         f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/{IDX}/_search' -H 'Content-Type: application/json' -d '{q}'"]
    return json.loads(subprocess.run(cmd,capture_output=True).stdout.decode('utf-8','replace'))

allc=es('{"size":1200,"query":{"term":{"doc_id":"%s"}},"_source":["content_with_weight","mom_id"]}'%DOC)
hits=allc['hits']['hits']
children=[h for h in hits if h['_source'].get('mom_id')]
parents=[h for h in hits if not h['_source'].get('mom_id')]
print(f'\nES: {len(hits)} total | {len(children)} children | {len(parents)} parents')

# child size distribution (children are what gets embedded+retrieved)
ctoks=sorted(len(enc.encode(h['_source'].get('content_with_weight',''))) for h in children)
if ctoks:
    print(f'\nCHILD sizes (cl100k tokens): min={ctoks[0]} p50={ctoks[len(ctoks)//2]} p90={ctoks[int(len(ctoks)*0.9)]} max={ctoks[-1]}')
    print(f'  children >256: {sum(1 for t in ctoks if t>256)}')
    print(f'  children >512: {sum(1 for t in ctoks if t>512)}')
    print(f'  children >2048 (the Qwen 40K embed handles these fine): {sum(1 for t in ctoks if t>2048)}')
    # show the biggest ones
    big=sorted(children,key=lambda h:-len(enc.encode(h['_source'].get('content_with_weight',''))))[:5]
    print('  biggest children:')
    for h in big:
        c=h['_source']['content_with_weight']; t=len(enc.encode(c))
        istab='<table>' in c
        sec=re.findall(r'\[S(\d+)',c)[:1]
        print(f'    tok={t} table={istab} sec={sec} | {c[:45].replace(chr(10)," ")}')
