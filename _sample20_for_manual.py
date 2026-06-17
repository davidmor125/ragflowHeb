"""Sample 20 random results for manual review.
Stratified: 10 from kw=PASS, 10 from kw=FAIL, deterministic seed for reproducibility.
"""
import sys, json, random, re
sys.stdout.reconfigure(encoding='utf-8')

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    data = json.load(f)

random.seed(42)

passed = [r for r in data['results'] if r['kw_passed']]
failed = [r for r in data['results'] if not r['kw_passed']]

random.shuffle(passed)
random.shuffle(failed)

sample = passed[:13] + failed[:7]  # 13 from passing pool, 7 from failing pool — proportional-ish
sample.sort(key=lambda r: r['n'])

def clean(answer):
    if not answer: return ""
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    return re.sub(r'\s+', ' ', out).strip()

def hebrew_only_segments(text, min_len=80):
    """Find contiguous Hebrew-rich segments (≥40% Hebrew)."""
    segs = []
    cur = []
    for c in text:
        if '֐' <= c <= '׿' or c in ' .,:;!?()0123456789-/%"':
            cur.append(c)
        else:
            if cur:
                s = ''.join(cur).strip()
                heb_chars = sum(1 for ch in s if '֐' <= ch <= '׿')
                if len(s) >= min_len and heb_chars / max(len(s),1) > 0.3:
                    segs.append(s)
            cur = []
    if cur:
        s = ''.join(cur).strip()
        heb_chars = sum(1 for ch in s if '֐' <= ch <= '׿')
        if len(s) >= min_len and heb_chars / max(len(s),1) > 0.3:
            segs.append(s)
    return segs

out = {'sample': []}
for r in sample:
    cleaned = clean(r['answer'])
    segs = hebrew_only_segments(cleaned, min_len=100)
    final_hebrew = max(segs, key=len) if segs else (cleaned[-1500:] if cleaned else '')
    out['sample'].append({
        'n': r['n'],
        'procedure': r['procedure'],
        'question': r['question'],
        'gold': r['expected'],
        'kw_passed': r['kw_passed'],
        'llm_verdict': r['llm_verdict'],
        'answer_full': cleaned,
        'answer_hebrew_only': final_hebrew,
    })

with open('/ragflow/_manual_sample20.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# Compact print
for s in out['sample']:
    print('━' * 100)
    print(f"n={s['n']} proc={s['procedure']} kw={'P' if s['kw_passed'] else 'F'} llm={s['llm_verdict'][0]}")
    print(f"Q: {s['question']}")
    print(f"GOLD: {(s['gold'] or '')[:500]}")
    print()
    print(f"HEB-ANSWER ({len(s['answer_hebrew_only'])} chars):")
    print(s['answer_hebrew_only'][:1800])
    print()
