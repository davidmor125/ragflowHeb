"""Run the 4 failed questions about proc=32904 through canvas v2 (now with top_n=5)."""
import sys, json, time, asyncio, re
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
from common import settings as ss
ss.init_settings()
from api.db.db_models import DB, UserCanvas
from agent.canvas import Canvas
DB.connect(reuse_if_open=True)

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'
PROC = '32904'
PER_Q_TIMEOUT = 240

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    eval_data = json.load(f)
questions = [r for r in eval_data['results'] if r['procedure'] == PROC and not r['kw_passed']]
print(f"Running {len(questions)} questions, top_n=5", flush=True)

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
        return f"[TIMEOUT after {PER_Q_TIMEOUT}s]\n{(final if final else ''.join(parts))[:1500]}", retr_size
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", retr_size
    return (final if final else "".join(parts)), retr_size


async def main():
    results = []
    for q in questions:
        print(f"\n========== n={q['n']}: {q['question']} ==========", flush=True)
        print(f"GOLD: {q['expected'][:300]}", flush=True)
        t0 = time.time()
        ans, retr = await ask(q['question'])
        elapsed = time.time() - t0
        out = re.sub(r'<think>.*?</think>', '', ans, flags=re.DOTALL)
        tail = out[-2000:] if len(out) > 2000 else out
        print(f"\n[{elapsed:.0f}s, retr={retr}]", flush=True)
        print(f"ANSWER:\n{tail}", flush=True)
        results.append({'n': q['n'], 'q': q['question'], 'gold': q['expected'], 'ans': ans, 'elapsed': elapsed, 'retr': retr})
    with open('/ragflow/_proc32904_topn5_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

asyncio.run(main())
