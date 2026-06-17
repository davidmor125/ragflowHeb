"""Run fixed canvas v2 on 20 previously-failed questions."""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'  # v2 (now fixed)
SAMPLE_FILE = '/ragflow/_picked_20_failed.json'
OUT = '/ragflow/eval_v2_fixed_20.json'

with open(SAMPLE_FILE, encoding='utf-8') as f:
    sample = json.load(f)['sample']

print(f"Running FIXED canvas v2 on {len(sample)} previously-failed questions", flush=True)
print()

async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    parts = []
    final = None
    retr_size = -1
    try:
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
                cname = data.get('component_name','')
                outputs = data.get('outputs') or {}
                if isinstance(outputs, dict) and 'formalized_content' in outputs:
                    retr_size = len(outputs.get('formalized_content','') or '')
                if (cname == 'Reply' or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", retr_size
    return (final if final else "".join(parts)), retr_size


async def main():
    out_data = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        t_q = time.time()
        ans, retr_size = await ask(q['question'])
        elapsed = time.time() - t_q
        eng = sum(1 for c in ans if 'a'<=c.lower()<='z')
        heb = sum(1 for c in ans if 0x590<=ord(c)<=0x5ff)
        ratio = heb / max(heb+eng, 1)
        elapsed_total = time.time() - t0
        eta = elapsed_total * (len(sample) - i) / max(i,1) / 60
        marker = '✓' if retr_size > 100 else '⚠'
        print(f"[{i:>2}/{len(sample)}] n={q['n']:>3} {elapsed:>4.0f}s heb={ratio:.2f} ans={len(ans)}c retr={retr_size}c {marker}  ETA={eta:.0f}m", flush=True)
        out_data.append({
            'n': q['n'],
            'procedure': q['procedure'],
            'question': q['question'],
            'gold': q['expected'],
            'old_kw_passed': q.get('kw_passed'),
            'old_llm_verdict': q.get('llm_verdict'),
            'fixed_canvas_answer': ans,
            'retrieval_size': retr_size,
            'elapsed_s': round(elapsed, 1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'completed': len(out_data), 'total': len(sample), 'results': out_data}, f, ensure_ascii=False, indent=2)
    print(f"\nDone. Total: {(time.time()-t0)/60:.1f}min", flush=True)

asyncio.run(main())
