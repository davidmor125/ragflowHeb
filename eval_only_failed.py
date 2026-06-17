"""Re-run ONLY the 4 questions that failed with the agent.
Update existing eval_agent_vs_baseline.json in-place."""
import sys, json, asyncio, time, re, os
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, Dialog, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID  = '54e45b8048a011f18e412992204f7aa3'
RESULTS_FILE = '/ragflow/eval_agent_vs_baseline.json'

with open(RESULTS_FILE, encoding='utf-8') as f:
    data = json.load(f)

failures = [r for r in data['results'] if not r['agent_passed']]
print(f"Re-running {len(failures)} failed questions through Agent")
for r in failures:
    print(f"  proc={r['procedure']}  Q: {r['question'][:60]}")
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
    by_n = {r['n']: r for r in data['results']}
    flips = 0
    for q in failures:
        t0 = time.time()
        ans, chunks = await ask_agent(q['question'])
        elapsed = time.time() - t0
        cleaned = clean(ans)
        ok, hits, total = grade(cleaned, q['expected'])
        flag = '★' if ok else ''
        print(f"  proc={q['procedure']:>5}  {('PASS' if ok else 'FAIL')} ({hits}/{total} kw, {elapsed:.0f}s){flag}")
        if not ok:
            print(f"    A: {cleaned[:150]}")
        if ok: flips += 1

        # Update record
        r = by_n[q['n']]
        r['agent_answer'] = cleaned
        r['agent_passed'] = ok
        r['agent_hits'] = hits
        r['agent_total'] = total
        r['agent_sec'] = round(elapsed, 1)

        # Save
        new_pass_baseline = sum(1 for x in data['results'] if x['baseline_passed'])
        new_pass_agent = sum(1 for x in data['results'] if x['agent_passed'])
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {'baseline_pass': new_pass_baseline, 'agent_pass': new_pass_agent, 'total': len(data['results'])},
                'results': data['results'],
            }, f, ensure_ascii=False, indent=2)

    n = len(data['results'])
    final_pass = sum(1 for x in data['results'] if x['agent_passed'])
    base_pass = sum(1 for x in data['results'] if x['baseline_passed'])
    print()
    print(f"Re-ran {len(failures)} prior failures, {flips} now PASS")
    print(f"OVERALL ({n}):  Baseline {base_pass}/{n} ({100*base_pass//n}%)  Agent {final_pass}/{n} ({100*final_pass//n}%)")

asyncio.run(main())
