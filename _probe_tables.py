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
    raw=subprocess.run(cmd,capture_output=True).stdout.decode('utf-8','replace')
    try:
        return json.loads(raw)
    except Exception:
        print('ES RAW (first 300):',raw[:300]); raise

# 1. How are S44/S66/S107 (big tables) stored? parent or split into children?
print('=== How TABLE sections are stored (S44, S66, S107) ===')
for sec in ['S44','S66','S107']:
    # search content containing the section id (no brackets to keep JSON clean)
    q='{"size":20,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"match_phrase":{"content_with_weight":"%s"}}]}},"_source":["content_with_weight","mom_id","available_int"]}'%(DOC,sec)
    r=es(q)
    hits=r['hits']['hits']
    parents=[h for h in hits if 'mom_id' not in h['_source'] or not h['_source'].get('mom_id')]
    children=[h for h in hits if h['_source'].get('mom_id')]
    # token sizes
    def tk(h): return len(enc.encode(h['_source'].get('content_with_weight','')))
    print(f'\n  {sec}: {len(hits)} ES docs mentioning it')
    print(f'     children (mom_id): {len(children)}  parents/standalone: {len(parents)}')
    has_table=[h for h in hits if '<table>' in h['_source'].get('content_with_weight','')]
    for h in has_table[:3]:
        isc = bool(h['_source'].get('mom_id'))
        print(f'     <table> doc: tok={tk(h)} is_child={isc} avail={h["_source"].get("available_int")}')

# 2. Are there ANY children that contain <table>? (would mean tables DID split)
print('\n=== Do any CHILDREN contain <table>? (tests the "tables not split" claim) ===')
q='{"size":0,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}},{"match_phrase":{"content_with_weight":"<table>"}}]}}}'%DOC
r=es(q)
print('  children containing <table>:',r['hits']['total']['value'])
q2='{"size":0,"query":{"bool":{"must":[{"term":{"doc_id":"%s"}},{"exists":{"field":"mom_id"}}]}}}'%DOC
r2=es(q2)
print('  total children:',r2['hits']['total']['value'])

# 3. So when a table-question hits, WHAT chunk granularity is returned?
print('\n=== When table question retrieves, what is returned (parent or child)? ===')
q='מהו הקוד הסודי המופיע בטבלת המפרט?'  # generic; use a real table q
qreal='אילו פרמטרים מפורטים באפיון API?'
r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':qreal,'dataset_ids':[DID],
    'page_size':4,'similarity_threshold':0.0,'vector_similarity_weight':0.3,
    'keyword':True,'cross_languages':['Hebrew','English']},timeout=120).json()
for c in r['data']['chunks']:
    t=len(enc.encode(c['content']))
    istab='<table>' in c['content']
    print(f'  sim={c["similarity"]:.3f} tok={t} has_table={istab} | {c["content"][:50].replace(chr(10)," ")}')
