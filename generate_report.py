import sys, json, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.load(open('test_results.json', encoding='utf-8'))

def clean_answer(text):
    """Strip <think> tags and citation markers from RAG answer."""
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?think>', '', text)
    text = re.sub(r'##\d+\$\$', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def smart_grade(answer, expected):
    """Match expected number even if RAG split it with spaces or commas (1327 vs 1 327 vs 1,327)."""
    if not answer or len(answer.strip()) < 5:
        return False, "EMPTY"
    clean = re.sub(r'##\d+\$\$', '', answer)
    # Normalize: remove all spaces and commas inside numbers — "1 327" -> "1327", "1,327" -> "1327"
    normalized = re.sub(r'(?<=\d)[,\s](?=\d)', '', clean)

    for kw in expected:
        kw_norm = re.sub(r'(?<=\d)[,\s](?=\d)', '', kw)
        if kw_norm.lower() in clean.lower() or kw_norm.lower() in normalized.lower():
            return True, kw
    return False, ", ".join(expected)

# Re-grade with smart matcher
fixed_pass = 0
for r in data['results']:
    answer_clean = clean_answer(r['answer'])
    ok, info = smart_grade(answer_clean, r['expected'])
    r['passed_v2'] = ok
    r['match_v2'] = info
    if ok:
        fixed_pass += 1

# Build the report
out = []
out.append("=" * 100)
out.append(f"  RAGFlow Hebrew RAG Test Report")
out.append(f"  Document: chap-1(1).pdf (Bank of Israel - Chapter 1)")
out.append(f"  LLM: gpt-oss:120b-cloud   |   VLM: gemma4:31b-cloud")
out.append(f"  Result (smart re-grade): {fixed_pass}/{data['total']} passed ({100*fixed_pass//data['total']}%)")
out.append(f"  Original auto-grade: {data['pass']}/{data['total']} ({100*data['pass']//data['total']}%)")
out.append("=" * 100)
out.append("")

for r in data['results']:
    icon = "✅" if r['passed_v2'] else "❌"
    expected = " / ".join(r['expected'])
    cleaned = clean_answer(r['answer'])
    if not cleaned:
        cleaned = "(תשובה ריקה — המודל החזיר רק thinking)"
    if len(cleaned) > 400:
        cleaned = cleaned[:400] + "..."

    out.append(f"┌─ Q{r['n']:02d} {icon} ({r['elapsed']:.1f}s)")
    out.append(f"│  שאלה: {r['question']}")
    out.append(f"│  תשובה צפויה: {expected}")
    out.append(f"│  תשובת RAG: {cleaned}")
    if r['passed_v2']:
        out.append(f"│  סטטוס: ✅ הצלחה — נמצאה התאמה: \"{r['match_v2']}\"")
    else:
        out.append(f"│  סטטוס: ❌ כישלון — לא נמצאה התאמה ל: {r['match_v2']}")
    out.append("└" + "─" * 99)
    out.append("")

# Summary
out.append("=" * 100)
out.append("  SUMMARY")
out.append("=" * 100)

passed_v2 = [r for r in data['results'] if r['passed_v2']]
failed_v2 = [r for r in data['results'] if not r['passed_v2']]
times = [r['elapsed'] for r in data['results']]

out.append(f"  ✅ Passed: {len(passed_v2)}/{len(data['results'])} ({100*len(passed_v2)//len(data['results'])}%)")
out.append(f"  ❌ Failed: {len(failed_v2)}/{len(data['results'])}")
out.append(f"  ⏱  Avg time per question: {sum(times)/len(times):.1f}s")
out.append(f"  ⏱  Min/Max: {min(times):.1f}s / {max(times):.1f}s")
out.append(f"  ⏱  Total runtime: {sum(times):.1f}s ({sum(times)/60:.1f} min)")
out.append("")
if failed_v2:
    out.append("  Remaining failures (real ones):")
    for r in failed_v2:
        out.append(f"    - Q{r['n']}: {r['question'][:80]}")
out.append("=" * 100)

report = "\n".join(out)

with open("test_report.txt", "w", encoding="utf-8") as f:
    f.write(report)
print(f"Report saved to test_report.txt ({len(report)} chars)")
print()
print(f"Smart re-grade: {fixed_pass}/{data['total']} ({100*fixed_pass//data['total']}%)")
print(f"Original:       {data['pass']}/{data['total']} ({100*data['pass']//data['total']}%)")
print(f"Diff: +{fixed_pass - data['pass']} (false negatives in original auto-grade)")
