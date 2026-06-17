"""Rescore the existing eval results after stripping the broken <think> tags
from the system answers. This addresses GPT-OSS reasoning-model streaming
where </think> closers are sprinkled mid-content."""
import sys, json, re, csv
sys.stdout.reconfigure(encoding='utf-8')

IN_JSON  = r'c:/develop/ragflow-main/eval_full_results.json'
OUT_JSON = r'c:/develop/ragflow-main/eval_full_results_rescored.json'
OUT_CSV  = r'c:/develop/ragflow-main/eval_full_results_rescored.csv'

HEB_STOP = {
    "של","על","כן","לא","את","אם","או","גם","כל","יש","זה","זו","זאת","כי","מה","מי","מן","כמו","אך","רק",
    "הוא","היא","אני","אנו","אתה","אתם","אנחנו","אלו","אלה","להיות","ניתן","יכול","צריך","נדרש","כאשר","אשר",
    "פי","תוך","בין","לפי","בעת","אחר","אחרי","לפני","במקרה","כאמור","לבין","אינו","אינה","וכך","כדי","מתוך",
    "בכל","בכך","וכן","כמה","איך","מהם","במהלך",
}

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


def clean_answer(answer):
    """Strip <think>...</think> blocks AND stray </think>/<think> tokens
    that the streaming layer scattered through the content."""
    if not answer: return answer
    # First strip well-formed <think>...</think> blocks (greedy across newlines)
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    # Then strip ANY remaining <think> or </think> tokens (the broken case)
    out = re.sub(r'</?think>', '', out)
    # Strip RAGFlow citation markers
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    # Collapse whitespace
    out = re.sub(r'\s+', ' ', out)
    return out.strip()


def grade(answer_clean, gold):
    if not answer_clean:
        return False, "EMPTY", 0, 0
    keywords = extract_keywords(gold)
    if not keywords:
        return bool(answer_clean.strip()), "(no-keywords)", 0, 0
    short_gold = (gold or "").strip()
    if len(short_gold) <= 3 and short_gold.lower() in answer_clean.lower():
        return True, short_gold, 1, 1
    hits = [kw for kw in keywords if kw.lower() in answer_clean.lower()]
    threshold = max(1, len(keywords) // 4)
    return (len(hits) >= threshold), (hits[0] if hits else ", ".join(keywords[:3])), len(hits), len(keywords)


with open(IN_JSON, encoding='utf-8') as f:
    data = json.load(f)

orig_pass = sum(1 for r in data['results'] if r['passed'])
flipped_to_pass = []
flipped_to_fail = []
new_pass = 0

for r in data['results']:
    cleaned = clean_answer(r['system_answer'])
    r['system_answer_clean'] = cleaned
    ok, match, hits, total = grade(cleaned, r['expected_answer'])
    was = r['passed']
    if ok and not was:
        flipped_to_pass.append(r)
    elif was and not ok:
        flipped_to_fail.append(r)
    r['passed'] = ok
    r['match_info'] = match
    r['keyword_hits'] = hits
    r['keywords_total'] = total
    if ok:
        new_pass += 1

n = len(data['results'])
data['summary']['answer_pass'] = new_pass
data['summary']['rescored'] = True

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(["#","שורת אקסל","פרוצדורה","נושא","תת-נושא","שאלה",
                "תשובה צפויה","תשובת המערכת (נקייה)",
                "תשובה PASS/FAIL","מילות מפתח שהותאמו",
                "רירנקר PASS/FAIL","דירוג קובץ נכון","ציון רירנקר","ציון top",
                "סה\"כ צ'אנקים","זמן (שנ')"])
    for r in data['results']:
        w.writerow([
            r["n"], r["row"], r["procedure"], r["topic"], r["subtopic"], r["question"],
            r["expected_answer"], r["system_answer_clean"],
            "PASS" if r["passed"] else "FAIL",
            f'{r["keyword_hits"]}/{r["keywords_total"]}',
            "PASS" if r["rerank_correct_doc_found"] else "FAIL",
            r["rerank_rank_of_correct_doc"] or "-",
            f'{r["rerank_score_of_correct_doc"]:.3f}' if r["rerank_score_of_correct_doc"] is not None else "-",
            f'{r["rerank_top_score"]:.3f}' if r["rerank_top_score"] is not None else "-",
            r["rerank_total_chunks"], r["elapsed_sec"],
        ])

print("=" * 70)
print(f"RESCORE RESULTS")
print("=" * 70)
print(f"  Original PASS:  {orig_pass}/{n}  ({100*orig_pass//n}%)")
print(f"  Rescored PASS:  {new_pass}/{n}  ({100*new_pass//n}%)")
print(f"  Net change:     {new_pass - orig_pass:+d}")
print(f"  FAIL→PASS flips: {len(flipped_to_pass)}")
print(f"  PASS→FAIL flips: {len(flipped_to_fail)}")
print()
print(f"Output: {OUT_JSON}")
print(f"Output: {OUT_CSV}")

if flipped_to_pass[:3]:
    print()
    print("Sample of NEWLY PASSING questions:")
    for r in flipped_to_pass[:5]:
        print(f"  proc={r['procedure']}  Q: {r['question'][:80]}")
        print(f"     match: {r['keyword_hits']}/{r['keywords_total']} keywords")

if flipped_to_fail:
    print()
    print(f"Sample of newly FAILING (regressions): {len(flipped_to_fail)}")
    for r in flipped_to_fail[:3]:
        print(f"  proc={r['procedure']}  Q: {r['question'][:80]}")
