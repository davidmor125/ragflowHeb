"""
Retrieval-quality audit: for a sample of test questions, call the RAGFlow
retrieval API and check whether the expected procedure doc appears in top-K.
Compares baseline (vector 0.3 + BM25, like the bank-eval dialog) vs reranker.
"""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE = 'http://localhost:9380/api/v1'
KEY = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
KB_ID = 'dc0091ca46e211f196f633ac796a3d7a'
H = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}

questions = json.load(open('test_questions_full.json', encoding='utf-8'))
# sample: every 4th question -> ~33 questions across procedures
sample = questions[::4]

def retrieve(q, rerank_id=None, top_k=1024, page_size=25):
    body = {
        'question': q,
        'dataset_ids': [KB_ID],
        'page': 1,
        'page_size': page_size,
        'similarity_threshold': 0.1,
        'vector_similarity_weight': 0.3,
        'top_k': top_k,
        'keyword': False,
    }
    if rerank_id:
        body['rerank_id'] = rerank_id
    r = requests.post(f'{BASE}/retrieval', json=body, headers=H, timeout=120)
    j = r.json()
    if j.get('code') != 0:
        return None, f"ERR {j.get('code')}: {str(j.get('message'))[:120]}"
    return j['data']['chunks'], None

def evaluate(rerank_id=None, label='baseline'):
    hits1 = hits5 = hits25 = 0
    n = 0
    errs = 0
    t0 = time.time()
    for item in sample:
        proc = item['procedure']
        chunks, err = retrieve(item['question'], rerank_id)
        if err:
            errs += 1
            if errs <= 2:
                print(f'  [{label}] {err}')
            if errs >= 3 and n == 0:
                return None  # API misconfigured, bail
            continue
        n += 1
        docnames = [c.get('document_keyword') or c.get('docnm_kwd') or '' for c in chunks]
        rank = next((i for i, d in enumerate(docnames) if proc in d), None)
        if rank is not None:
            hits25 += 1
            if rank < 5: hits5 += 1
            if rank < 1: hits1 += 1
    dt = time.time() - t0
    print(f'[{label}] n={n} errs={errs}  hit@1={hits1}/{n}  hit@5={hits5}/{n}  hit@25={hits25}/{n}  ({dt:.0f}s)')
    return dict(n=n, h1=hits1, h5=hits5, h25=hits25)

print(f'Sample size: {len(sample)} questions')
base = evaluate(None, 'baseline (no rerank, vw=0.3)')
for rid in ['qllama/bge-reranker-v2-m3:latest@Ollama', 'BAAI/bge-reranker-v2-m3@HuggingFace']:
    res = evaluate(rid, f'rerank={rid.split("@")[0]}')
    if res is None:
        print(f'  -> reranker {rid} not usable')
