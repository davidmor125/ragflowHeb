"""Run all 132 questions through the agent (now pointing at hozrim).
Save incrementally so a partial run isn't lost."""
import sys, json, asyncio, time, re, os
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
QFILE    = '/ragflow/test_questions_full.json'
OUT      = '/ragflow/eval_agent_full_132.json'

with open(QFILE, encoding='utf-8') as f:
    all_qs = json.load(f)
for i, q in enumerate(all_qs, 1):
    q['n'] = i

print(f"Total: {len(all_qs)} questions, agent pointed at hozrim (646 docs)")
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

def grade(answer_clean, gold):
    if not answer_clean: return False, 0, 0
    keywords = extract_keywords(gold)
    if not keywords: return bool(answer_clean.strip()), 0, 0
    short = (gold or "").strip()
    if len(short) <= 3 and short.lower() in answer_clean.lower():
        return True, 1, 1
    hits = [kw for kw in keywords if kw.lower() in answer_clean.lower()]
    threshold = max(1, len(keywords) // 4)
    return (len(hits) >= threshold), len(hits), len(keywords)


async def ask_agent(question):
    from agent.canvas import Canvas
    fresh = UserCanvas.get(UserCanvas.id == AGENT_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    answer_parts = []
    final_message_content = None
    chunks_used = []
    try:
        async for ev in cnvs.run(query=question):
            if not isinstance(ev, dict): continue
            data_field = ev.get("data") or {}
            event_type = ev.get("event", "")
            if event_type == "message":
                c = data_field.get("content") if isinstance(data_field, dict) else None
                if c: answer_parts.append(c)
            elif event_type == "message_end":
                c = data_field.get("content") if isinstance(data_field, dict) else None
                if c: final_message_content = c
            elif event_type == "node_finished":
                if isinstance(data_field, dict):
                    cname = data_field.get("component_name", "")
                    if cname == "Reply" or data_field.get("component_type") == "Message":
                        outputs = data_field.get("outputs") or {}
                        if isinstance(outputs, dict) and outputs.get("content"):
                            final_message_content = outputs["content"]
            if isinstance(data_field, dict):
                if data_field.get("chunks"): chunks_used = data_field["chunks"]
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", []
    answer = final_message_content if final_message_content else "".join(answer_parts)
    return answer, chunks_used


async def main():
    results = []
    agent_pass = 0
    t_start = time.time()
    for i, q in enumerate(all_qs, 1):
        t0 = time.time()
        ans, chunks = await ask_agent(q['question'])
        elapsed = time.time() - t0
        cleaned = clean(ans)
        ok, hits, total = grade(cleaned, q['expected_answer'])
        if ok: agent_pass += 1
        elapsed_total = time.time() - t_start
        eta_min = (elapsed_total * (len(all_qs) - i) / i) / 60 if i > 0 else 0
        ok_str = '✅' if ok else '❌'
        print(f"[{i:>3}/{len(all_qs)}] {ok_str} {hits}/{total}kw {elapsed:>4.0f}s  proc={q['procedure']:>5}  pass={agent_pass}/{i} ({100*agent_pass//max(i,1)}%)  ETA={eta_min:.0f}m")
        results.append({
            'n': i, 'procedure': q['procedure'], 'topic': q.get('topic',''),
            'question': q['question'], 'expected': q['expected_answer'],
            'agent_answer': cleaned, 'agent_passed': ok,
            'agent_hits': hits, 'agent_total': total, 'agent_sec': round(elapsed, 1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {'agent_pass': agent_pass, 'total': len(results),
                            'elapsed_total_sec': round(elapsed_total, 1)},
                'results': results,
            }, f, ensure_ascii=False, indent=2)

    n = len(results)
    print()
    print("=" * 60)
    print(f"FINAL ({n} questions, total {(time.time()-t_start)/60:.1f}m)")
    print(f"  Agent: {agent_pass}/{n} ({100*agent_pass//n}%)")

asyncio.run(main())
