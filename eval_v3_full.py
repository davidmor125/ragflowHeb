"""Run all 132 questions through Agentic RAG v3 (with self-check loop)."""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '05aea11c495211f180b9273574f6967d'  # banking_agentic_rag_v3
QFILE    = '/ragflow/test_questions_full.json'
OUT      = '/ragflow/eval_agent_v3_132.json'

with open(QFILE, encoding='utf-8') as f:
    all_qs = json.load(f)
for i, q in enumerate(all_qs, 1):
    q['n'] = i

print(f"Running {len(all_qs)} questions through Agentic RAG v3 (Self-Check loop)")
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
    selfcheck_grade = None
    used_retry = False
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
                if cname == 'Self_Check' and isinstance(outputs, dict):
                    selfcheck_grade = outputs.get('category_name','')
                if cname == 'Reply_RETRY':
                    used_retry = True
                if (cname == 'Reply_PASS' or cname == 'Reply_RETRY') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", None, False
    return (final if final else "".join(answer_parts)), selfcheck_grade, used_retry


async def main():
    results = []
    pass_count = 0
    retry_count = 0
    t_start = time.time()
    for i, q in enumerate(all_qs, 1):
        t0 = time.time()
        ans, sc_grade, used_retry = await ask(q['question'])
        elapsed = time.time() - t0
        ok, hits, total = grade(ans, q['expected_answer'])
        if ok: pass_count += 1
        if used_retry: retry_count += 1
        elapsed_total = time.time() - t_start
        eta_min = (elapsed_total * (len(all_qs) - i) / i) / 60 if i > 0 else 0
        ok_str = '✅' if ok else '❌'
        path = '↻' if used_retry else '→'
        print(f"[{i:>3}/{len(all_qs)}] {ok_str}{path} {hits}/{total}kw {elapsed:>4.0f}s  proc={q['procedure']:>5}  pass={pass_count}/{i} ({100*pass_count//max(i,1)}%)  retries={retry_count}  ETA={eta_min:.0f}m")
        results.append({
            'n': i, 'procedure': q['procedure'], 'topic': q.get('topic',''),
            'question': q['question'], 'expected': q['expected_answer'],
            'answer': ans, 'passed': ok,
            'selfcheck': sc_grade, 'used_retry': used_retry,
            'hits': hits, 'total': total, 'elapsed': round(elapsed, 1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {'pass': pass_count, 'total': len(results), 'retries': retry_count,
                            'elapsed_total_sec': round(elapsed_total, 1)},
                'results': results,
            }, f, ensure_ascii=False, indent=2)
    n = len(results)
    print()
    print("=" * 60)
    print(f"FINAL ({n} questions, total {(time.time()-t_start)/60:.1f}m)")
    print(f"  Agent v3: {pass_count}/{n} ({100*pass_count//n}%)")
    print(f"  Used RETRY path: {retry_count}/{n}")

asyncio.run(main())
