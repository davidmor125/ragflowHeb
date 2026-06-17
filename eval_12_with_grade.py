"""Run fixed canvas v2 on the 12 originally-failed questions.
Print PASS/FAIL after each question (keyword-based + Hebrew presence).
Hard timeout 180s per question.
"""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'  # v2 fixed
SAMPLE_FILE = '/ragflow/_picked_12.json'
OUT = '/ragflow/eval_12_fixed.json'
PER_Q_TIMEOUT = 180

with open(SAMPLE_FILE, encoding='utf-8') as f:
    sample = json.load(f)['sample']

print(f"Running FIXED canvas v2 on {len(sample)} originally-failed questions", flush=True)
print(f"Hard timeout per question: {PER_Q_TIMEOUT}s\n", flush=True)

HEB_STOP = {"של","על","כן","לא","את","אם","או","גם","כל","יש","זה","זו","זאת","כי","מה","מי","מן","כמו","אך","רק","הוא","היא","אני","אנו","אתה","אתם","אנחנו","אלו","אלה","להיות","ניתן","יכול","צריך","נדרש","כאשר","אשר","פי","תוך","בין","לפי","בעת","אחר","אחרי","לפני","במקרה","כאמור","לבין","אינו","אינה","וכך","כדי","מתוך","בכל","בכך","וכן","כמה","איך","מהם","במהלך"}

def extract_keywords(gold, k=8):
    if not gold: return []
    cleaned = re.sub(r'[^\w֐-׿\s\d.%]', ' ', gold)
    seen, out = set(), []
    for tok in cleaned.split():
        t = tok.strip().strip('.').strip()
        if len(t) < 3 and not (t.isdigit() or re.fullmatch(r'\d+\.?\d*', t)): continue
        if t in HEB_STOP or t in seen: continue
        seen.add(t); out.append(t)
        if len(out) >= k: break
    return out

def grade(answer, gold):
    if not answer or '[TIMEOUT' in answer or '[ERROR' in answer:
        return False, 0, 0
    keywords = extract_keywords(gold)
    if not keywords:
        return bool(answer.strip()), 0, 0
    short = (gold or "").strip()
    if len(short) <= 3 and short.lower() in answer.lower():
        return True, 1, 1
    hits = [kw for kw in keywords if kw.lower() in answer.lower()]
    threshold = max(1, len(keywords) // 4)
    return (len(hits) >= threshold), len(hits), len(keywords)

async def ask_with_timeout(question):
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
                cname = data.get('component_name','')
                outputs = data.get('outputs') or {}
                if isinstance(outputs, dict) and 'formalized_content' in outputs:
                    retr_size = len(outputs.get('formalized_content','') or '')
                if (cname == 'Reply' or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']

    try:
        await asyncio.wait_for(_run(), timeout=PER_Q_TIMEOUT)
    except asyncio.TimeoutError:
        ans = (final if final else "".join(parts))
        return f"[TIMEOUT after {PER_Q_TIMEOUT}s] {ans[:1500]}", retr_size
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", retr_size
    return (final if final else "".join(parts)), retr_size


async def main():
    out_data = []
    pass_count = 0
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        t_q = time.time()
        ans, retr_size = await ask_with_timeout(q['question'])
        elapsed = time.time() - t_q
        ok, hits, total = grade(ans, q['expected'])
        if ok: pass_count += 1
        flag = '✅ PASS' if ok else '❌ FAIL'
        timeout_flag = ' [TIMEOUT]' if '[TIMEOUT' in ans else ''
        retr_flag = '' if retr_size > 100 else ' [empty retrieval!]'
        running_score = f"{pass_count}/{i}"
        print(f"[{i:>2}/{len(sample)}] n={q['n']:>3} {elapsed:>4.0f}s  {flag} {hits}/{total}kw  retr={retr_size}c{timeout_flag}{retr_flag}  running={running_score}", flush=True)
        out_data.append({
            'n': q['n'],
            'procedure': q['procedure'],
            'question': q['question'],
            'gold': q['expected'],
            'answer': ans,
            'retrieval_size': retr_size,
            'elapsed_s': round(elapsed, 1),
            'passed': ok,
            'hits': hits,
            'total_kw': total,
            'timed_out': '[TIMEOUT' in ans,
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'completed': len(out_data), 'total': len(sample), 'pass_count': pass_count, 'results': out_data}, f, ensure_ascii=False, indent=2)
    print()
    print(f"FINAL: {pass_count}/{len(sample)} PASS  ({pass_count*100/len(sample):.0f}%)", flush=True)
    print(f"Total time: {(time.time()-t0)/60:.1f}min", flush=True)

asyncio.run(main())
