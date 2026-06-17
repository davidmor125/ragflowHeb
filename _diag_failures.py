"""Deep diagnosis of the 15 still-failing questions.
For each one: extract Hebrew sections, count thinking-leak ratio,
look for patterns of failure (no Hebrew / wrong Hebrew / ran out of tokens / no retrieval).
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

with open('/ragflow/eval_step1_max_rounds.json', encoding='utf-8') as f:
    data = json.load(f)

HEB = lambda c: '֐' <= c <= '׿'

def hebrew_only(text):
    """Extract contiguous Hebrew runs from text."""
    runs = re.findall(r'[֐-׿\d\s.,:;!?\-\(\)%/]+', text)
    runs = [r.strip() for r in runs if r.strip() and any(HEB(c) for c in r) and len(r) > 5]
    return runs

def english_run_count(text):
    """Count significant runs of English (>30 ascii letters in a row)."""
    return len(re.findall(r'[a-zA-Z][a-zA-Z\s.,:;\(\)\-_]{30,}', text))

def hebrew_chars(text):
    return sum(1 for c in text if HEB(c))

def english_chars(text):
    return sum(1 for c in text if 'a' <= c.lower() <= 'z')


print("="*100)
print("FAILURE FORENSICS — 15 questions still failing after Step 1")
print("="*100)
print()

for r in data['results']:
    if r['passed_now']:
        continue
    ans = r.get('answer_step1', '')
    n = r['n']; proc = r['procedure']; q = r['question'][:70]
    expected = r['expected'][:120]

    h_chars = hebrew_chars(ans)
    e_chars = english_chars(ans)
    total = max(len(ans), 1)
    h_pct = h_chars * 100 // total
    e_pct = e_chars * 100 // total

    runs = hebrew_only(ans)
    last_heb = runs[-1] if runs else ""
    n_steps = len(re.findall(r'(?i)\bstep\s*\d+', ans))
    n_search = len(re.findall(r'(?i)search_my_dateset|search.*dataset', ans))

    print(f"--- n={n}  proc={proc}  hits={r['hits']}/{r['total']}  len={len(ans)}  ---")
    print(f"Q: {q}")
    print(f"Expected (head): {expected}")
    print(f"Heb={h_pct}%  Eng={e_pct}%  steps={n_steps}  searches={n_search}  heb_runs={len(runs)}")
    if last_heb:
        print(f"LAST_HEB ({len(last_heb)} chars): {last_heb[:300]}")
    else:
        print(f"NO HEBREW AT ALL.  First 200 chars: {ans[:200]}")
    print()
