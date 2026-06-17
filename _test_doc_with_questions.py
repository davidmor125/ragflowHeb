"""End-to-end test on doc proc=32904 (ביטול כרטיסי אשראי):
1. Re-parse with all our fixes (split_table headers, auto_keywords)
2. Run the 4 failed questions through canvas v2
3. Manually grade each answer
"""
import sys, json, time, asyncio, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, Document, Task, UserCanvas
from api.db.services.document_service import DocumentService
from api.db.services.task_service import TaskService
from rag.nlp import search
from agent.canvas import Canvas
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'
PROC = '32904'
DOC_NAME = f'טסט/{PROC}.html'
CANVAS_ID = '22c30f2049db11f18c556f95756a453d'  # pipeline v2 (fixed)

# Load failed questions on this proc
with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    eval_data = json.load(f)
questions = [r for r in eval_data['results'] if r['procedure'] == PROC and not r['kw_passed']]
print(f"Failed questions on proc={PROC}: {len(questions)}", flush=True)
for q in questions:
    print(f"  n={q['n']}: {q['question']}", flush=True)
print()

# Find doc
doc = next(d for d in Document.select().where(Document.kb_id == KB) if d.name == DOC_NAME)
print(f"Doc id={doc.id} size={doc.size}\n", flush=True)

# === Step 1: Re-parse ===
print("=== Step 1: Re-parse ===", flush=True)
DocumentService.clear_chunk_num_when_rerun(doc.id)
DocumentService.update_by_id(doc.id, {"run": "1", "progress": 0, "progress_msg": "", "chunk_num": 0, "token_num": 0})
TaskService.filter_delete([Task.doc_id == doc.id])
if ss.docStoreConn.index_exist(search.index_name(TENANT), KB):
    ss.docStoreConn.delete({"doc_id": doc.id}, search.index_name(TENANT), KB)
doc = Document.get(Document.id == doc.id)
DocumentService.run(TENANT, doc.to_dict(), {})
print("triggered, polling...", flush=True)

start = time.time()
last_msg = ""
while time.time() - start < 1800:
    time.sleep(10)
    d = Document.get(Document.id == doc.id)
    elapsed = time.time() - start
    msg = (d.progress_msg or '').strip().split('\n')[-1] if d.progress_msg else ''
    if msg != last_msg:
        print(f"  [{elapsed:.0f}s] run={d.run} progress={d.progress:.2f}  {msg[:100]}", flush=True)
        last_msg = msg
    if str(d.run) in ("3", "4"):
        break
d = Document.get(Document.id == doc.id)
print(f"Parse done. chunks={d.chunk_num}\n", flush=True)

# === Step 2: Verify chunks ===
print("=== Step 2: Verify chunks ===", flush=True)
res = ss.docStoreConn.search(['content_with_weight','important_kwd'], [], {'kb_id': KB, 'doc_id': doc.id}, [], {}, 0, 200,
                              [search.index_name(TENANT)], [KB])
items = list(ss.docStoreConn.get_fields(res, ['content_with_weight','important_kwd']).values())
sizes = sorted(len((p.get('content_with_weight','') or '')) for p in items if isinstance(p, dict))
with_kwd = sum(1 for p in items if isinstance(p, dict) and p.get('important_kwd'))
print(f"  chunks: {len(items)}", flush=True)
print(f"  size median={sizes[len(sizes)//2]} max={sizes[-1]}", flush=True)
print(f"  with auto_keywords: {with_kwd}/{len(items)}", flush=True)
# show 3 sample keywords
for p in items[:3]:
    if isinstance(p, dict) and p.get('important_kwd'):
        print(f"  kwd: {p.get('important_kwd')}", flush=True)
print()

# === Step 3: Run questions through canvas ===
print("=== Step 3: Run failed questions through canvas v2 ===", flush=True)

PER_Q_TIMEOUT = 240

async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    parts = []
    final = None
    retr_size = -1
    async def _run():
        nonlocal parts, final, retr_size
        async for ev in cnvs.run(query=question):
            if not isinstance(ev, dict): continue
            data = ev.get('data') or {}
            et = ev.get('event','')
            if et == 'message':
                c = data.get('content') if isinstance(data, dict) else None
                if c: parts.append(c)
            elif et == 'message_end':
                c = data.get('content') if isinstance(data, dict) else None
                if c: final = c
            elif et == 'node_finished' and isinstance(data, dict):
                outputs = data.get('outputs') or {}
                if isinstance(outputs, dict) and 'formalized_content' in outputs:
                    retr_size = len(outputs.get('formalized_content','') or '')
                if (data.get('component_name') == 'Reply' or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    try:
        await asyncio.wait_for(_run(), timeout=PER_Q_TIMEOUT)
    except asyncio.TimeoutError:
        return f"[TIMEOUT after {PER_Q_TIMEOUT}s] {(final if final else ''.join(parts))[:1500]}", retr_size
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", retr_size
    return (final if final else "".join(parts)), retr_size

async def main():
    results = []
    for q in questions:
        print(f"\n--- n={q['n']}: {q['question']} ---", flush=True)
        print(f"GOLD: {q['expected'][:300]}", flush=True)
        t0 = time.time()
        ans, retr_size = await ask(q['question'])
        elapsed = time.time() - t0
        # Strip thinking/take final hebrew
        out = re.sub(r'<think>.*?</think>', '', ans, flags=re.DOTALL)
        # Take last 1500 chars (final answer)
        tail = out[-2000:] if len(out) > 2000 else out
        print(f"\nELAPSED: {elapsed:.0f}s  retr_size={retr_size}", flush=True)
        print(f"ANSWER (last 2000c):\n{tail}", flush=True)
        results.append({'n': q['n'], 'q': q['question'], 'gold': q['expected'], 'ans': ans, 'elapsed': elapsed, 'retr': retr_size})
    with open('/ragflow/_test_proc32904_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDone. saved to _test_proc32904_results.json", flush=True)

asyncio.run(main())
