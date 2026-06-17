"""Step 2: re-run still-failing 15 questions through gemma4:31b-cloud agent.

Hypothesis: gemma4 is not a reasoning model -> no English thinking-leak ->
clean Hebrew answer that the keyword grader can match.
"""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '8448ab80498e11f195832b167e47396c'  # banking_agentic_rag_gemma
PRIOR    = '/ragflow/eval_step1_max_rounds.json'
OUT      = '/ragflow/eval_step2_gemma.json'

with open(PRIOR, encoding='utf-8') as f:
    prior = json.load(f)

still_failing = [r for r in prior['results'] if not r['passed_now']]
print(f"Step 2: re-running {len(still_failing)} still-failing questions through gemma4:31b-cloud")
print()

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

def clean(answer):
    if not answer: return ""
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    return re.sub(r'\s+', ' ', out).strip()

def grade(answer, gold):
    if not answer: return False, 0, 0
    keywords = extract_keywords(gold)
    if not keywords: return bool(answer.strip()), 0, 0
    short = (gold or "").strip()
    if len(short) <= 3 and short.lower() in answer.lower():
        return True, 1, 1
    hits = [kw for kw in keywords if kw.lower() in answer.lower()]
    threshold = max(1, len(keywords) // 4)
    return (len(hits) >= threshold), len(hits), len(keywords)


async def ask(question):
    fresh = UserCanvas.get(UserCanvas.id == AGENT_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    answer_parts = []
    final = None
    try:
        async for ev in cnvs.run(query=question):
            if not isinstance(ev, dict): continue
            data = ev.get('data') or {}
            et = ev.get('event','')
            if et == 'message':
                c = data.get('content') if isinstance(data, dict) else None
                if c: answer_parts.append(c)
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
    return final if final else "".join(answer_parts)


async def main():
    results = []
    flipped = 0
    t_start = time.time()
    for i, q in enumerate(still_failing, 1):
        t0 = time.time()
        ans = await ask(q['question'])
        elapsed = time.time() - t0
        cleaned = clean(ans)
        ok, hits, total = grade(cleaned, q['expected'])
        if ok: flipped += 1
        flag = '✅' if ok else '❌'
        flip = ' ★' if ok else ''
        print(f"[{i:>2}/{len(still_failing)}] {flag} {hits}/{total}kw {elapsed:>4.0f}s  proc={q['procedure']:>5}  flipped={flipped}/{i}{flip}")
        results.append({
            'n': q['n'], 'procedure': q['procedure'],
            'question': q['question'], 'expected': q['expected'],
            'answer_gemma': cleaned, 'passed_now': ok,
            'hits': hits, 'total': total, 'elapsed': round(elapsed, 1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {'total': len(still_failing), 'flipped': flipped, 'completed': len(results)},
                'results': results,
            }, f, ensure_ascii=False, indent=2)

    n = len(results)
    print()
    print("=" * 60)
    print(f"STEP 2 (gemma4:31b-cloud): {flipped}/{n} flipped to PASS")
    print(f"Total time: {(time.time()-t_start)/60:.1f}min")
    overall = 117 + flipped
    print(f"Overall projected: {overall}/132 = {overall*100/132:.1f}%")

asyncio.run(main())
