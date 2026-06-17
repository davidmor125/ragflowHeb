"""LLM-as-judge using qwen3:14b LOCAL (no Ollama Cloud quota needed).

For each of the 132 results, send (question, gold, answer) to qwen3:14b
and ask: "Does the answer correctly address the question, given the gold reference?"
Returns PASS/FAIL + short reason.

We strip thinking-leak first so the judge sees only the actual answer text.
"""
import sys, json, re, time, asyncio
import httpx
sys.stdout.reconfigure(encoding='utf-8')

OLLAMA_URL = "http://host.docker.internal:11434/api/chat"
MODEL = "qwen3:14b"
INFILE = '/ragflow/best_132.json'
OUTFILE = '/ragflow/eval_llm_judged.json'

def clean(answer):
    if not answer: return ""
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    return re.sub(r'\s+', ' ', out).strip()

def hebrew_tail(text, max_chars=1500):
    """Take the last hebrew-rich window of the answer."""
    if not text: return ""
    # find positions where Hebrew chars appear
    heb_positions = [i for i,c in enumerate(text) if '֐' <= c <= '׿']
    if not heb_positions:
        return text[-max_chars:]
    last = heb_positions[-1]
    start = max(0, last - max_chars)
    return text[start:last+1]

PROMPT_TEMPLATE = """You are evaluating answers to banking-procedure questions in Hebrew.

QUESTION: {question}

GOLD REFERENCE ANSWER:
{gold}

CANDIDATE ANSWER:
{answer}

Task: Does the CANDIDATE ANSWER correctly answer the QUESTION based on the same facts as the GOLD REFERENCE?
- It does NOT need to use the same words.
- It does NOT need to be complete; partial-but-correct is acceptable.
- It MUST not contradict the gold reference on the key fact.
- If the candidate is empty, English-only thinking with no real answer, or asks the user a clarifying question instead of answering, that's FAIL.

Respond with EXACTLY one word on the first line: PASS or FAIL
Then on the second line, a short reason (max 15 words, in English).
/no_think
"""

async def judge(client, question, gold, answer):
    answer_clean = clean(answer)
    answer_view = hebrew_tail(answer_clean, 1500) if answer_clean else "(empty)"
    gold_short = (gold or "")[:1500]
    prompt = PROMPT_TEMPLATE.format(question=question, gold=gold_short, answer=answer_view)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 8192},
        "think": False,
    }
    try:
        resp = await client.post(OLLAMA_URL, json=payload, timeout=180)
        resp.raise_for_status()
        out = resp.json()
        text = (out.get('message') or {}).get('content', '') or ''
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        first_line = text.splitlines()[0] if text.strip() else ''
        verdict = 'PASS' if 'PASS' in first_line.upper() else 'FAIL'
        reason = ' '.join(text.splitlines()[1:])[:200] if len(text.splitlines()) > 1 else ''
        return verdict, reason, text
    except Exception as e:
        return 'ERROR', f"{type(e).__name__}: {str(e)[:200]}", ''

async def main():
    with open(INFILE, encoding='utf-8') as f:
        data = json.load(f)
    items = data['results']
    print(f"Judging {len(items)} answers with {MODEL} (local Ollama)")
    print()
    judged = []
    pass_n = 0
    kw_pass_n = 0
    flips_to_pass = 0
    flips_to_fail = 0
    t0 = time.time()
    async with httpx.AsyncClient() as client:
        for i, r in enumerate(items, 1):
            verdict, reason, raw = await judge(client, r['question'], r['expected'], r['answer'])
            ok = verdict == 'PASS'
            if ok: pass_n += 1
            if r['kw_passed']: kw_pass_n += 1
            if ok and not r['kw_passed']:
                flips_to_pass += 1
                marker = '🆙'
            elif not ok and r['kw_passed']:
                flips_to_fail += 1
                marker = '⚠️'
            else:
                marker = '  '
            elapsed = time.time() - t0
            avg = elapsed / i
            eta = avg * (len(items) - i) / 60
            print(f"[{i:>3}/{len(items)}] {verdict:<5} {marker} kw={'P' if r['kw_passed'] else 'F'} llm_pass={pass_n}/{i}  proc={r['procedure']:>5}  {reason[:60]}  ETA={eta:.0f}m")
            judged.append({
                **r,
                'llm_verdict': verdict,
                'llm_reason': reason,
            })
            if i % 10 == 0 or i == len(items):
                with open(OUTFILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        'summary': {
                            'total': len(items),
                            'kw_passed': kw_pass_n,
                            'llm_passed': pass_n,
                            'completed': i,
                            'flips_to_pass': flips_to_pass,
                            'flips_to_fail': flips_to_fail,
                        },
                        'results': judged,
                    }, f, ensure_ascii=False, indent=2)
    print()
    print("=" * 60)
    print(f"Keyword grader: {kw_pass_n}/{len(items)} = {kw_pass_n*100/len(items):.1f}%")
    print(f"LLM judge:      {pass_n}/{len(items)} = {pass_n*100/len(items):.1f}%")
    print(f"  ↑ flipped FAIL→PASS: {flips_to_pass}")
    print(f"  ↓ flipped PASS→FAIL: {flips_to_fail}")
    print(f"Total time: {(time.time()-t0)/60:.1f}min")

asyncio.run(main())
