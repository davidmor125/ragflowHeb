"""Deeper diagnosis: rerank config, chunk metadata, chunk boundaries, scoring breakdown."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import pymysql, requests
from elasticsearch import Elasticsearch

cfg = dict(host='localhost', port=3306, user='root', password='infini_rag_flow', database='rag_flow', charset='utf8mb4')
conn = pymysql.connect(**cfg, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

KB_ID = 'dc0091ca46e211f196f633ac796a3d7a'
DOC_ID = 'f84ca83246e211f196f633ac796a3d7a'
DIALOG_ID = 'cf68bf1a46f011f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

# ============================================================
# 1. Dialog reranker config
# ============================================================
print("=" * 80, flush=True)
print("1. DIALOG CONFIG (is reranker active?)", flush=True)
print("=" * 80, flush=True)
cur.execute("SELECT id, name, llm_id, rerank_id, top_n, top_k, similarity_threshold, vector_similarity_weight FROM dialog WHERE id=%s", (DIALOG_ID,))
d = cur.fetchone()
for k, v in d.items():
    print(f"  {k}: {v!r}", flush=True)

# Tenant LLM rerank
cur.execute("SELECT * FROM tenant_llm WHERE tenant_id=%s AND model_type='rerank'", (TENANT,))
print("\n  rerank model registered:", flush=True)
for r in cur.fetchall():
    print(f"    factory={r['llm_factory']!r}  llm_name={r['llm_name']!r}  api_base={r['api_base']!r}", flush=True)

# ============================================================
# 2. KB-level rerank config
# ============================================================
print("\n" + "=" * 80, flush=True)
print("2. KB CONFIG (does the KB have a reranker default?)", flush=True)
print("=" * 80, flush=True)
cur.execute("SELECT id, name, embd_id, parser_id, parser_config FROM knowledgebase WHERE id=%s", (KB_ID,))
k = cur.fetchone()
print(f"  embd_id   : {k['embd_id']}", flush=True)
print(f"  parser_id : {k['parser_id']}", flush=True)
pc = k['parser_config']
if pc:
    pc_obj = json.loads(pc) if isinstance(pc, str) else pc
    print(f"  parser_config keys: {list(pc_obj.keys())}", flush=True)
    print(f"  raptor enabled  : {pc_obj.get('raptor', {}).get('use_raptor')}", flush=True)
    print(f"  graphrag enabled: {pc_obj.get('graphrag', {}).get('use_graphrag')}", flush=True)
    print(f"  auto_keywords  : {pc_obj.get('auto_keywords')}", flush=True)
    print(f"  auto_questions : {pc_obj.get('auto_questions')}", flush=True)
    print(f"  chunk_token_num: {pc_obj.get('chunk_token_num')}", flush=True)
    print(f"  topn_tags      : {pc_obj.get('topn_tags')}", flush=True)
    print(f"  layout_recognize: {pc_obj.get('layout_recognize')}", flush=True)

# ============================================================
# 3. Inspect chunk metadata directly from ES
# ============================================================
print("\n" + "=" * 80, flush=True)
print("3. CHUNK METADATA (important_kwd, question_kwd, title_tks per chunk)", flush=True)
print("=" * 80, flush=True)

es = Elasticsearch("http://localhost:1200", basic_auth=("elastic", "infini_rag_flow"))
INDEX = f"ragflow_{TENANT}"

resp = es.search(
    index=INDEX,
    body={
        "size": 100,
        "query": {"bool": {"must": [
            {"term": {"kb_id": KB_ID}},
            {"term": {"doc_id": DOC_ID}}
        ]}},
        "_source": ["content_with_weight", "important_kwd", "question_kwd",
                    "content_ltks", "title_tks", "title_sm_tks", "name_kwd",
                    "tag_feas", "knowledge_graph_kwd"],
    }
)
hits = resp['hits']['hits']
print(f"\n  Total chunks: {len(hits)}", flush=True)

# stats on metadata fields
field_filled = {f: 0 for f in ['important_kwd', 'question_kwd', 'title_tks', 'tag_feas', 'knowledge_graph_kwd']}
for h in hits:
    src = h['_source']
    for f in field_filled:
        v = src.get(f)
        if v is not None and v != [] and v != "":
            field_filled[f] += 1

print("\n  Metadata coverage (chunks with non-empty value):", flush=True)
for f, c in field_filled.items():
    print(f"    {f:25s}: {c:3d}/{len(hits)} = {100*c//len(hits)}%", flush=True)

# Look at the GOLD chunks for each failed question
GOLD_PHRASES = {
    "Q69 ויזה כאל": "מכניסת חוק שירותי תשלום לתוקף, על הבנק לאפשר ביטול כרטיס בהודעה",
    "Q71 מקס":     "מכניסת חוק שירותי תשלום לתוקף, על הבנק לאפשר ביטול כרטיס בהודעה",
    "Q72 עמלות":   "ריכוז תעריפוני",
}

print("\n  Gold chunks: full metadata\n", flush=True)
seen = set()
for label, phrase in GOLD_PHRASES.items():
    print(f"  --- {label} ---  searching for: {phrase!r}", flush=True)
    for h in hits:
        content = (h['_source'].get('content_with_weight') or '')
        if phrase in content and h['_id'] not in seen:
            seen.add(h['_id'])
            src = h['_source']
            print(f"    chunk_id : {h['_id']}", flush=True)
            print(f"    content  ({len(content)}c): {content[:300].replace(chr(10),' ')}...", flush=True)
            print(f"    important_kwd  : {src.get('important_kwd')!r}", flush=True)
            print(f"    question_kwd   : {src.get('question_kwd')!r}", flush=True)
            print(f"    title_tks      : {(src.get('title_tks') or '')[:200]!r}", flush=True)
            print(f"    tag_feas       : {src.get('tag_feas')!r}", flush=True)
            print(f"    knowledge_graph_kwd: {src.get('knowledge_graph_kwd')!r}", flush=True)
            print(flush=True)
            break

# ============================================================
# 4. CHUNK BOUNDARIES — does each chunk start mid-sentence?
# ============================================================
print("=" * 80, flush=True)
print("4. CHUNK QUALITY — sizes and boundaries", flush=True)
print("=" * 80, flush=True)

sizes = []
for h in hits:
    c = h['_source'].get('content_with_weight') or ''
    sizes.append(len(c))

sizes.sort()
print(f"\n  Chunk size dist (chars):", flush=True)
print(f"    min   : {sizes[0]}", flush=True)
print(f"    p25   : {sizes[len(sizes)//4]}", flush=True)
print(f"    median: {sizes[len(sizes)//2]}", flush=True)
print(f"    p75   : {sizes[3*len(sizes)//4]}", flush=True)
print(f"    max   : {sizes[-1]}", flush=True)

# Check first/last chars of a few chunks
print(f"\n  Sample chunks - first/last 100 chars:", flush=True)
for h in hits[:5]:
    c = h['_source'].get('content_with_weight') or ''
    head = c[:100].replace("\n", " ")
    tail = c[-100:].replace("\n", " ")
    print(f"    [START] {head}", flush=True)
    print(f"    [ END ] ...{tail}", flush=True)
    print(flush=True)

# ============================================================
# 5. Did the rerank actually run? Check retrieval response
# ============================================================
print("=" * 80, flush=True)
print("5. RETRIEVAL SCORING BREAKDOWN (vector vs term vs rerank similarity)", flush=True)
print("=" * 80, flush=True)

API_KEY  = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
BASE_URL = 'http://localhost:9380'
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Try with rerank model attached
RERANK_ID = 'BAAI/bge-reranker-v2-m3@HuggingFace'

for label, q in [
    ("Q69 ויזה כאל", "איך ניתן לבטל כרטיס מסוג ויזה כאל?"),
    ("Q72 עמלות",     "כמה עולה לבטל כרטיס אשראי?"),
]:
    print(f"\n  --- {label}: {q} ---", flush=True)
    for use_rerank in [False, True]:
        body = {
            "question": q,
            "dataset_ids": [KB_ID],
            "document_ids": [DOC_ID],
            "similarity_threshold": 0.1,
            "vector_similarity_weight": 0.3,
            "top_k": 1024,
            "page_size": 10,
        }
        if use_rerank:
            body["rerank_id"] = RERANK_ID
        r = requests.post(f"{BASE_URL}/api/v1/retrieval", json=body, headers=HEADERS, timeout=120)
        if r.status_code != 200:
            print(f"    [rerank={use_rerank}] HTTP {r.status_code}: {r.text[:200]}", flush=True)
            continue
        j = r.json()
        if j.get('code') != 0:
            print(f"    [rerank={use_rerank}] error: {j.get('message')}", flush=True)
            continue
        chunks = j['data'].get('chunks', [])[:10]
        print(f"\n    [{'WITH RERANK' if use_rerank else 'NO  RERANK'}]  top-10:", flush=True)
        for i, c in enumerate(chunks):
            content = (c.get('content_with_weight') or c.get('content') or '')
            sim = c.get('similarity', 0); vsim = c.get('vector_similarity', 0); tsim = c.get('term_similarity', 0)
            # check if this is a gold chunk for this question
            is_gold = False
            if label.startswith("Q69") and "מכניסת חוק שירותי תשלום" in content:
                is_gold = True
            elif label.startswith("Q72") and "ריכוז תעריפוני" in content:
                is_gold = True
            mark = " ★GOLD★ " if is_gold else "        "
            print(f"      {mark}{i+1:2d} | sim={sim:.3f} vsim={vsim:.3f} tsim={tsim:.3f} | {content[:100].replace(chr(10),' ')}", flush=True)

cur.close(); conn.close()
