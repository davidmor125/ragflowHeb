"""For every 'לא תקין' row, check whether the gold-answer text actually appears
in the extracted HTML. If it does → chunking pushed the wrong window. If it
doesn't → the HTML really doesn't contain the answer (Excel ground-truth
is wrong / answer is in a different procedure)."""
import sys
import openpyxl
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from tools.scripts.eval_html_qa import extract_text_from_html
from tools.scripts.eval_excel_qa import select_doc_for_question

XLSX = Path(r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_filled.xlsx")
HTML_DIR = Path(r"C:/develop/html_output/_eval_report/newtest/טסט")

wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

failures = []
for i in range(5, len(rows)):
    row = rows[i]
    nohel = row[1]
    answer = row[5]
    verdict = str(row[9] or "").strip()
    if not (nohel and answer):
        continue
    if verdict.startswith("לא תקין"):
        failures.append((i, str(nohel), str(row[4] or ""), str(row[6] or ""), str(answer), verdict))

print(f"failures so far: {len(failures)}\n")
text_cache = {}
for i, nohel, q, gold, model_ans, verdict in failures:
    fn = f"{nohel}.html"
    if fn not in text_cache:
        text_cache[fn] = extract_text_from_html(HTML_DIR / fn)
    full = text_cache[fn]
    win = select_doc_for_question(full, q)

    # First 4 distinctive words from the gold answer
    gold_words = [w for w in gold.replace("\n", " ").split() if len(w) >= 3][:6]
    needle_full = sum(1 for w in gold_words if w in full)
    needle_window = sum(1 for w in gold_words if w in win)

    print(f"=== ROW {i} (נוהל={nohel}) ===")
    print(f"  שאלה:       {q[:100]}")
    print(f"  תשובת זהב:  {gold[:100]}")
    print(f"  תשובת מודל: {model_ans[:120]}")
    print(f"  full text:  {len(full)} chars; gold-words found in full: {needle_full}/{len(gold_words)}")
    print(f"  window:     {len(win)} chars; gold-words found in window: {needle_window}/{len(gold_words)}")
    diagnosis = (
        "ANSWER NOT IN HTML AT ALL — Excel ground-truth points to wrong procedure"
        if needle_full == 0
        else "ANSWER IN HTML BUT NOT IN WINDOW — chunking missed it"
        if needle_window < needle_full // 2
        else "ANSWER IN WINDOW — model failed to find/use it"
    )
    print(f"  → {diagnosis}")
    print()
