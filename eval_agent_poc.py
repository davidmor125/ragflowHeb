"""Run the 27 POC questions through the banking_agentic_rag agent
and through the baseline bank-eval-poc dialog (for comparison).

Both use the same KB (hozrim_poc, 20 files), same LLM (gemma4:31b-cloud),
same reranker. The only difference is the Agent has self-refinement
(up to 5 retrieval rounds with query rewrite). The baseline does single-shot
retrieval+answer.
"""
import sys, json, asyncio, time, re, os
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, Dialog, UserCanvas
from api.db.services.dialog_service import async_chat
from api.db.services.canvas_service import UserCanvasService
DB.connect(reuse_if_open=True)

AGENT_ID  = '54e45b8048a011f18e412992204f7aa3'   # banking_agentic_rag
DIALOG_ID = '92e82d60487a11f1a37a31aeaf1accf8'   # bank-eval-poc
QFILE     = '/ragflow/test_questions_full.json'
OUT       = '/ragflow/eval_agent_vs_baseline.json'

with open(QFILE, encoding='utf-8') as f:
    all_qs = json.load(f)

# Add a sequential index (the JSON file has no 'n' field)
for i, q in enumerate(all_qs, 1):
    q['n'] = i

# Filter to the POC questions
POC_PROCS = {'14940','17802','18049','20071','21801','31604','32328','32904',
             '34838','36792','36967','37340','5088','66577','7528','82078',
             '83745','90398','91018','92422'}
poc_qs_all = [q for q in all_qs if str(q['procedure']) in POC_PROCS]

# Pick 20 representative questions: 1 per procedure (first match)
seen = set()
poc_qs = []
for q in poc_qs_all:
    if q['procedure'] not in seen:
        seen.add(q['procedure'])
        poc_qs.append(q)

print(f"POC questions: {len(poc_qs)}")

dialog = Dialog.get(Dialog.id == DIALOG_ID)
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
print(f"Baseline dialog: {dialog.name}  llm={dialog.llm_id}  top_n={dialog.top_n}")
print(f"Agent canvas:    {canvas.title}")

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


# Use canvas runner for the agent
async def ask_agent(question):
    """Run the question through the agent canvas. Fresh Canvas per question
    so history/state doesn't bleed between questions."""
    from agent.canvas import Canvas

    # Re-fetch the canvas DSL fresh — new Canvas instance for each question
    fresh = UserCanvas.get(UserCanvas.id == AGENT_ID)
    cnvs = Canvas(json.dumps(fresh.dsl), tenant_id=fresh.user_id, canvas_id=fresh.id)
    answer_parts = []
    final_message_content = None
    chunks_used = []
    try:
        async for ev in cnvs.run(query=question):
            if not isinstance(ev, dict):
                continue
            data = ev.get("data") or {}
            event_type = ev.get("event", "")
            # Capture text fragments emitted by the Message component
            if event_type == "message":
                content = data.get("content") if isinstance(data, dict) else None
                if content:
                    answer_parts.append(content)
            elif event_type == "message_end":
                content = data.get("content") if isinstance(data, dict) else None
                if content:
                    final_message_content = content
            elif event_type == "node_finished":
                if isinstance(data, dict):
                    cname = data.get("component_name", "")
                    if cname == "Reply" or data.get("component_type") == "Message":
                        outputs = data.get("outputs") or {}
                        if isinstance(outputs, dict) and outputs.get("content"):
                            final_message_content = outputs["content"]
            # Capture chunks produced by Retrieval tool calls
            if isinstance(data, dict):
                if data.get("chunks"):
                    chunks_used = data["chunks"]
                ref = data.get("reference") or (data.get("output") or {}).get("reference")
                if ref and isinstance(ref, dict) and ref.get("chunks"):
                    chunks_used = ref["chunks"]
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", []
    # Prefer the consolidated final message; fall back to the streamed parts
    answer = final_message_content if final_message_content else "".join(answer_parts)
    return answer, chunks_used


async def ask_dialog(question):
    answer, chunks = "", []
    try:
        async for ch in async_chat(dialog, [{"role": "user", "content": question}], stream=True):
            if not isinstance(ch, dict): continue
            if ch.get("answer"): answer = ch["answer"]
            ref = ch.get("reference") or {}
            if ref.get("chunks"): chunks = ref["chunks"]
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {str(e)[:200]}]", []
    return answer, chunks


async def main():
    results = []
    agent_pass = 0
    base_pass = 0
    for i, q in enumerate(poc_qs, 1):
        print(f"\n[{i}/{len(poc_qs)}] proc={q['procedure']} {q['question'][:60]}")

        # Baseline
        t0 = time.time()
        b_ans, b_chunks = await ask_dialog(q['question'])
        b_elapsed = time.time() - t0
        b_clean = clean(b_ans)
        b_ok, b_hits, b_total = grade(b_clean, q['expected_answer'])

        # Agent
        t0 = time.time()
        a_ans, a_chunks = await ask_agent(q['question'])
        a_elapsed = time.time() - t0
        a_clean = clean(a_ans)
        a_ok, a_hits, a_total = grade(a_clean, q['expected_answer'])

        if b_ok: base_pass += 1
        if a_ok: agent_pass += 1

        flip = ""
        if a_ok and not b_ok: flip = " ★ FAIL→PASS"
        elif b_ok and not a_ok: flip = " ⚠ PASS→FAIL"

        print(f"  baseline {'PASS' if b_ok else 'FAIL'} ({b_hits}/{b_total} kw, {b_elapsed:.1f}s)")
        print(f"  agent    {'PASS' if a_ok else 'FAIL'} ({a_hits}/{a_total} kw, {a_elapsed:.1f}s){flip}")
        if not a_ok:
            print(f"    A: {a_clean[:120]}")

        results.append({
            'n': q['n'],
            'procedure': q['procedure'],
            'question': q['question'],
            'expected': q['expected_answer'],
            'baseline_answer': b_clean, 'baseline_passed': b_ok,
            'baseline_hits': b_hits, 'baseline_total': b_total, 'baseline_sec': round(b_elapsed,1),
            'agent_answer': a_clean, 'agent_passed': a_ok,
            'agent_hits': a_hits, 'agent_total': a_total, 'agent_sec': round(a_elapsed,1),
        })
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {'baseline_pass': base_pass, 'agent_pass': agent_pass, 'total': len(results)},
                'results': results,
            }, f, ensure_ascii=False, indent=2)

    n = len(results)
    print()
    print("=" * 60)
    print(f"OUTCOME on {n} POC questions")
    print(f"  Baseline (single-shot):  {base_pass}/{n} ({100*base_pass//n}%)")
    print(f"  Agent (multi-round):     {agent_pass}/{n} ({100*agent_pass//n}%)")
    print(f"  Net change: {agent_pass - base_pass:+d}")

asyncio.run(main())
