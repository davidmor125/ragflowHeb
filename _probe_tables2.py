import sys, json, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
import tiktoken
enc=tiktoken.get_encoding('cl100k_base')
DOC='339d485066f611f1a56021ba47a3a9e1'
IDX='ragflow_2507563a42bd11f1a6bba9e87ac7a32c'

def es(q):
    cmd=['docker','exec','docker-ragflow-cpu-1','sh','-c',
         f"curl -s -u elastic:infini_rag_flow -XPOST 'http://es01:9200/{IDX}/_search' -H 'Content-Type: application/json' -d '{q}'"]
    return json.loads(subprocess.run(cmd,capture_output=True).stdout.decode('utf-8','replace'))

# pull ALL docs for this file (parents+children), analyze in python
q='{"size":1000,"query":{"term":{"doc_id":"%s"}},"_source":["content_with_weight","mom_id","available_int"]}'%DOC
r=es(q)
hits=r['hits']['hits']
print(f'total ES docs: {len(hits)}')

parents=[]; children=[]
for h in hits:
    s=h['_source']; c=s.get('content_with_weight','')
    rec={'tok':len(enc.encode(c)),'table':'<table>' in c,'mom':bool(s.get('mom_id')),
         'avail':s.get('available_int'),'head':c[:50].replace('\n',' '),
         'sec':re.findall(r'\[S(\d+)',c)[:2]}
    (children if rec['mom'] else parents).append(rec)

print(f'\nparents (no mom_id): {len(parents)}   children (mom_id): {len(children)}')

# THE KEY QUESTION: do children ever contain <table>? i.e. did tables split?
tab_children=[c for c in children if c['table']]
tab_parents=[c for c in parents if c['table']]
print(f'\n=== TABLES ===')
print(f'  children containing <table>: {len(tab_children)}')
print(f'  parents containing <table>:  {len(tab_parents)}')
print(f'  -> if children-with-table==0, tables were NOT split (stayed whole as parent+1 child copy)')

# For a big table section, show: parent size vs its children sizes
print(f'\n=== sizes: table-bearing CHILDREN (these are what retrieval matches) ===')
for c in sorted(tab_children,key=lambda x:-x['tok'])[:8]:
    print(f'  child tok={c["tok"]:5d} sec={c["sec"]} | {c["head"]}')
print(f'\n=== biggest CHILDREN overall (table or not) ===')
for c in sorted(children,key=lambda x:-x['tok'])[:8]:
    print(f'  child tok={c["tok"]:5d} table={c["table"]} sec={c["sec"]} | {c["head"]}')

# distribution
toks=sorted(c['tok'] for c in children)
print(f'\nchild token dist: min={toks[0]} p50={toks[len(toks)//2]} p90={toks[int(len(toks)*0.9)]} max={toks[-1]}')
print(f'children >512 tok: {sum(1 for t in toks if t>512)}  >2048: {sum(1 for t in toks if t>2048)}')
print(f'of the >512 children, how many are tables: {sum(1 for c in children if c["tok"]>512 and c["table"])}')
