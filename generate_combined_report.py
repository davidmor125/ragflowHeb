import sys, json, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data1 = json.load(open('test_results.json', encoding='utf-8'))
data2 = json.load(open('test_results_60.json', encoding='utf-8'))

all_results = data1['results'] + data2['results']
total = len(all_results)

def clean_answer(text):
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?think>', '', text)
    text = re.sub(r'##\d+\$\$', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def smart_grade(answer_clean, expected):
    if not answer_clean or len(answer_clean.strip()) < 5:
        return False, "EMPTY"
    if answer_clean.startswith("[ERROR"):
        return False, "ERROR"
    # Strip spaces/commas inside numbers - "1 327" -> "1327"
    normalized = re.sub(r'(?<=\d)[,\s](?=\d)', '', answer_clean)
    # Also try matching with optional minus/dash variations (Hebrew uses different dash characters)
    norm_dashes = re.sub(r'[‒–—−﹣－]', '-', normalized)
    for kw in expected:
        kw_norm = re.sub(r'(?<=\d)[,\s](?=\d)', '', kw)
        kw_norm_dashes = re.sub(r'[‒–—−﹣－]', '-', kw_norm)
        candidates = [kw.lower(), kw_norm.lower(), kw_norm_dashes.lower()]
        targets = [answer_clean.lower(), normalized.lower(), norm_dashes.lower()]
        for c in candidates:
            for t in targets:
                if c in t:
                    return True, kw
    return False, ", ".join(expected)

# Re-grade everything
fixed_pass = 0
for r in all_results:
    cleaned = clean_answer(r['answer'])
    ok, info = smart_grade(cleaned, r['expected'])
    r['passed_v2'] = ok
    r['match_v2'] = info
    if ok:
        fixed_pass += 1

# Sections for the combined report
SECTIONS = {
    "Q01-15: Table א'-1 (Yearly key data 2013-2018)": (1, 15),
    "Q16-19: Image א'-1 (Unemployment & vacancies)": (16, 19),
    "Q20-22: Image א'-2 (Inflation components)": (20, 22),
    "Q23: Image א'-3 (OECD comparison)": (23, 23),
    "Q24-25: Image א'-4 (Real exchange rate)": (24, 25),
    "Q26-27: Image א'-5 (Per-capita GDP)": (26, 27),
    "Q28-29: Image א'-6 (Interest expectations)": (28, 29),
    "Q30: Image א'-7 (Multi-country indicators)": (30, 30),
    "Q31-33: Image א'-8 (Labor force scenarios)": (31, 33),
    "Q34-38: Table א'-3 (Long-term forecasts)": (34, 38),
    "Q39-40: Table א'-4 (Productivity scenarios)": (39, 40),
    "Q41-50: Text & cross-table reasoning": (41, 50),
    # 60 new
    "Q51-60: Year-by-year data 2014-2015": (51, 60),
    "Q61-65: Year 2017 specifics": (61, 65),
    "Q66-68: Year 2014 specifics": (66, 68),
    "Q69-72: Year 2016 specifics": (69, 72),
    "Q73-76: Cross-year arithmetic": (73, 76),
    "Q77-81: Trade & Exchange rates": (77, 81),
    "Q82-86: Markets & Real interest": (82, 86),
    "Q87-90: Detailed text understanding": (87, 90),
    "Q91-93: Image א'-1 details": (91, 93),
    "Q94-97: Image א'-2 details": (94, 97),
    "Q98-99: Image א'-3 details": (98, 99),
    "Q100-101: Image א'-4 details": (100, 101),
    "Q102-104: Image א'-5 details": (102, 104),
    "Q105-106: Image א'-6 details": (105, 106),
    "Q107-109: Image א'-8 details": (107, 109),
    "Q110-111: Forecast tables details": (110, 111),
}

out = []
out.append("=" * 110)
out.append("  RAGFlow Hebrew RAG — Comprehensive Test Report (110 Questions)")
out.append("  Document: chap-1(1).pdf  |  Bank of Israel — Annual Report Chapter 1")
out.append("  LLM: gpt-oss:120b-cloud   |   VLM: gemma4:31b-cloud")
out.append("=" * 110)
out.append("")
out.append(f"  Result: {fixed_pass}/{total} passed = {100*fixed_pass/total:.1f}%")
out.append("")

for section_title, (start, end) in SECTIONS.items():
    section_results = [r for r in all_results if start <= r['n'] <= end]
    if not section_results:
        continue
    sec_pass = sum(1 for r in section_results if r['passed_v2'])
    out.append("")
    out.append("─" * 110)
    out.append(f"  {section_title}    ({sec_pass}/{len(section_results)})")
    out.append("─" * 110)
    for r in section_results:
        icon = "✅" if r['passed_v2'] else "❌"
        cleaned = clean_answer(r['answer'])
        if not cleaned:
            cleaned = "(empty - thinking only)"
        if len(cleaned) > 250:
            cleaned = cleaned[:250] + "..."
        expected = " / ".join(r['expected'])
        out.append("")
        out.append(f"  {icon} Q{r['n']:03d}  ({r['elapsed']:.1f}s)")
        out.append(f"     שאלה:        {r['question']}")
        out.append(f"     תשובה צפויה: {expected}")
        out.append(f"     תשובת RAG:   {cleaned}")

# Final summary
out.append("")
out.append("=" * 110)
out.append("  FINAL SUMMARY")
out.append("=" * 110)

passed_v2 = [r for r in all_results if r['passed_v2']]
failed_v2 = [r for r in all_results if not r['passed_v2']]
times = [r['elapsed'] for r in all_results]

out.append(f"  ✅ Passed: {len(passed_v2)}/{total}  ({100*len(passed_v2)/total:.1f}%)")
out.append(f"  ❌ Failed: {len(failed_v2)}/{total}  ({100*len(failed_v2)/total:.1f}%)")
out.append("")
out.append(f"  ⏱  Avg time per question:  {sum(times)/len(times):.1f}s")
out.append(f"  ⏱  Min/Max:                 {min(times):.1f}s / {max(times):.1f}s")
out.append(f"  ⏱  Total runtime:           {sum(times):.0f}s ({sum(times)/60:.1f} min)")
out.append("")

# Breakdown by category
categories = {
    "Table A'-1 yearly data (Q1-15, 51-72)": list(range(1, 16)) + list(range(51, 73)),
    "Image questions (Q16-33, 91-109)": list(range(16, 34)) + list(range(91, 110)),
    "Forecast tables A'-3 & A'-4 (Q34-40, 110-111)": list(range(34, 41)) + [110, 111],
    "Text understanding & cross-year (Q41-50, 73-90)": list(range(41, 51)) + list(range(73, 91)),
}

out.append("  BREAKDOWN BY CATEGORY:")
for cat_name, cat_nums in categories.items():
    cat_results = [r for r in all_results if r['n'] in cat_nums]
    if cat_results:
        cat_pass = sum(1 for r in cat_results if r['passed_v2'])
        pct = 100 * cat_pass / len(cat_results)
        out.append(f"    • {cat_name}:  {cat_pass}/{len(cat_results)} ({pct:.0f}%)")

out.append("")
if failed_v2:
    out.append(f"  REAL FAILURES ({len(failed_v2)}):")
    for r in failed_v2:
        out.append(f"    Q{r['n']:03d}: {r['question'][:90]}")
        out.append(f"          expected: {r['expected']}")

out.append("")
out.append("=" * 110)

report = "\n".join(out)
with open("test_report_110.txt", "w", encoding="utf-8") as f:
    f.write(report)

print(f"Report saved to test_report_110.txt ({len(report)} chars)")
print()
print(f"Final score: {fixed_pass}/{total} ({100*fixed_pass/total:.1f}%)")
print()

# Print summary breakdown
print("BREAKDOWN BY CATEGORY:")
for cat_name, cat_nums in categories.items():
    cat_results = [r for r in all_results if r['n'] in cat_nums]
    if cat_results:
        cat_pass = sum(1 for r in cat_results if r['passed_v2'])
        pct = 100 * cat_pass / len(cat_results)
        print(f"  • {cat_name}:  {cat_pass}/{len(cat_results)} ({pct:.0f}%)")

print()
print(f"REAL FAILURES ({len(failed_v2)}):")
for r in failed_v2:
    print(f"  Q{r['n']:03d}: {r['question'][:90]}")
    print(f"        expected: {r['expected']}")
