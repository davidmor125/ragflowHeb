"""Run the pipeline on the same 20 questions we manually reviewed.
Saves answers so you can read them all in one pass.
"""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '708c8bca49cf11f1bcd66b39e390ca8c'
SAMPLE_FILE = '/ragflow/_manual_sample20.json'
OUT = '/ragflow/eval_pipeline_20.json'

def clean_thinking(answer):
    """Remove gemma's pseudo-thinking lines that come BEFORE the final answer.
    Heuristic: gemma's final answer is usually the last block of consecutive Hebrew lines
    after a '*Final Answer Construction:*' or just at the very end.
    """
    if not answer: return ""
    # Strip <think>
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    # Look for the last "Final" marker
    m = re.search(r'\*Final[^*]*?\*\s*\n', out)
    if m:
        out = out[m.end():]
    # Last fallback: if there's a duplicated Hebrew block, take the last one
    return out.strip()

with open(SAMPLE_FILE, encoding='utf-8') as f:
    sample = json.load(f)['sample']

print(f"Running pipeline on {len(sample)} sample questions")
print()

async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == CANVAS_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    parts = []
    final = None
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
                if (cname == 'Reply' or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]"
    return final if final else "".join(parts)


async def main():
    out_data = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        t_q = time.time()
        ans = await ask(q['question'])
        elapsed = time.time() - t_q
        cleaned = clean_thinking(ans)
        eng = sum(1 for c in cleaned if 'a'<=c.lower()<='z')
        heb = sum(1 for c in cleaned if '֐'<=c<='׿')
        ratio = heb / max(heb+eng, 1)
        elapsed_total = time.time() - t0
        eta = elapsed_total * (len(sample) - i) / max(i,1) / 60
        print(f"[{i:>2}/{len(sample)}] n={q['n']:>3} proc={q['procedure']:>5} {elapsed:>4.0f}s heb={ratio:.2f} len={len(cleaned)}  ETA={eta:.0f}m")
        out_data.append({
            'n': q['n'],
            'procedure': q['procedure'],
            'question': q['question'],
            'gold': q['gold'],
            'old_answer_hebrew_only': q.get('answer_hebrew_only',''),
            'old_kw_passed': q.get('kw_passed'),
            'old_llm_verdict': q.get('llm_verdict'),
            'pipeline_answer': cleaned,
            'pipeline_answer_raw': ans,
            'pipeline_elapsed_s': round(elapsed, 1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'completed': len(out_data), 'total': len(sample), 'results': out_data}, f, ensure_ascii=False, indent=2)
    print()
    print(f"Done. Total: {(time.time()-t0)/60:.1f}min")

asyncio.run(main())
