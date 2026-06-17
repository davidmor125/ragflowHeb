"""For 5 sample disagreements (kw=PASS, llm=FAIL), show exactly what the judge saw."""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    data = json.load(f)

def clean(answer):
    if not answer: return ""
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    return re.sub(r'\s+', ' ', out).strip()

def hebrew_tail(text, max_chars=1500):
    if not text: return ""
    heb_positions = [i for i,c in enumerate(text) if '֐' <= c <= '׿']
    if not heb_positions:
        return text[-max_chars:]
    last = heb_positions[-1]
    start = max(0, last - max_chars)
    return text[start:last+1]

# Get disagreements
disagree = [r for r in data['results'] if r['kw_passed'] and r['llm_verdict']=='FAIL']
print(f"Total disagreements (kw=PASS, llm=FAIL): {len(disagree)}")
print()

# Show first 5 in detail
for r in disagree[:5]:
    print("=" * 90)
    print(f"n={r['n']}  proc={r['procedure']}")
    print(f"Q: {r['question']}")
    print()
    print(f"GOLD (head 400):")
    print(f"  {(r['expected'] or '')[:400]}")
    print()
    print(f"RAW ANSWER (last 800 chars of original):")
    print(f"  {(r['answer'] or '')[-800:]}")
    print()
    cleaned = clean(r['answer'])
    view = hebrew_tail(cleaned, 1500)
    print(f"WHAT JUDGE SAW (cleaned -> hebrew_tail, first 800):")
    print(f"  {view[:800]}")
    print()
    print(f"JUDGE VERDICT: {r['llm_verdict']}")
    print(f"JUDGE REASON:  {r['llm_reason']}")
    print()
