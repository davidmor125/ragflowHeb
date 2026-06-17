"""Analyze failures from the full 132-question eval run."""
import sys, json, re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

JARGON = [
    "תמנון", "תנופה", "דולב", "סניפומט", "מקוון", "פל\"ת", 'פל"ת',
    "גלא\"ש", 'גלא"ש', "מו\"ח", 'מו"ח', "מת\"ף", 'מת"ף',
    "ני\"ע", 'ני"ע', "מט\"ח", 'מט"ח', "מט\"י", 'מט"י',
    "כא\"ש", 'כא"ש', "ס.פ.", "ס\"פ", 'ס"פ',
    "POP CODE", "EMV", "EDI", "סוויפט", "BENEFRES",
    "הכר את הלקוח", "מועדון", "פנקסי המחאות", "סיווג",
    "חוצץ", "פקיד מבצע", "סניף מפנה", "סניף מבצע",
]

def has_jargon(text):
    return any(t in (text or "") for t in JARGON)

with open(r'c:/develop/ragflow-main/eval_full_results.json', encoding='utf-8') as f:
    data = json.load(f)
results = data['results']
total = len(results)

# Categorize each result
fails = [r for r in results if not r['passed']]
passes = [r for r in results if r['passed']]

print(f"Total: {total}  pass: {len(passes)}  fail: {len(fails)}")
print()

# 1. Failures by topic
topic_pass = Counter()
topic_fail = Counter()
for r in results:
    if r['passed']: topic_pass[r['topic']] += 1
    else:           topic_fail[r['topic']] += 1
all_topics = set(topic_pass) | set(topic_fail)

print("=== Pass rate by topic (sorted by # questions) ===")
rows = []
for t in all_topics:
    p, f = topic_pass[t], topic_fail[t]
    rows.append((t, p, f, p+f, 100*p//(p+f) if (p+f) else 0))
rows.sort(key=lambda x: -x[3])
for t, p, f, n, pct in rows:
    bar = '█' * (pct // 5) + '░' * ((100-pct)//5)
    print(f"  {t:25}  {p:>3}/{n:<3} ({pct:>3}%)  {bar}")

print()

# 2. Failure by jargon presence
print("=== Pass rate split by 'has banking jargon in question' ===")
jp_pass = sum(1 for r in passes if has_jargon(r['question']))
jp_fail = sum(1 for r in fails if has_jargon(r['question']))
nj_pass = len(passes) - jp_pass
nj_fail = len(fails) - jp_fail
total_j = jp_pass + jp_fail
total_nj = nj_pass + nj_fail
print(f"  WITH jargon:    {jp_pass}/{total_j}  ({100*jp_pass//total_j if total_j else 0}%)")
print(f"  WITHOUT jargon: {nj_pass}/{total_nj}  ({100*nj_pass//total_nj if total_nj else 0}%)")

print()

# 3. Why did failures fail? Bucket them
print("=== Failure root cause buckets ===")
b_no_doc = []          # rerank didn't find correct doc at all
b_low_rank = []        # rerank found but rank > 3
b_top3_but_wrong = []  # rerank found in top-3 but answer wrong
b_top1_but_wrong = []  # rerank #1 but answer still wrong
b_empty_match = []     # answer says "מידע אינו קיים" effectively

EMPTY_PAT = re.compile(r"(אינו|אינה|לא נמצא|לא מצוין|לא מופיע|המידע אינו)")

for r in fails:
    found = r['rerank_correct_doc_found']
    rank = r['rerank_rank_of_correct_doc'] or 0
    ans = r['system_answer'] or ""
    if not found:
        b_no_doc.append(r)
    elif rank > 3:
        b_low_rank.append(r)
    elif rank == 1:
        b_top1_but_wrong.append(r)
    else:
        b_top3_but_wrong.append(r)

print(f"  Rerank MISSED correct doc entirely:        {len(b_no_doc)}")
print(f"  Rerank found at rank > 3:                  {len(b_low_rank)}")
print(f"  Rerank in top-3 but LLM answered wrong:    {len(b_top3_but_wrong)}")
print(f"  Rerank #1 but LLM answered wrong:          {len(b_top1_but_wrong)}")

# Empty answer check
empty_count = sum(1 for r in fails if EMPTY_PAT.search(r['system_answer'] or ''))
print(f"  Of all fails, answer says 'no info':       {empty_count}")

print()
print("=== Sample of each failure bucket ===")
for label, bucket in [
    ("MISSED", b_no_doc),
    ("RANK > 3", b_low_rank),
    ("TOP-3 but wrong answer", b_top3_but_wrong),
    ("TOP #1 but wrong answer", b_top1_but_wrong),
]:
    print(f"\n  --- {label} ({len(bucket)}) ---")
    for r in bucket[:3]:
        print(f"    proc={r['procedure']}  Q: {r['question'][:75]}")
        print(f"      expected: {(r['expected_answer'] or '')[:80]}")
        print(f"      got:      {(r['system_answer'] or '')[:80]}")
