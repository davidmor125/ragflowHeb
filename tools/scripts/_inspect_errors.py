"""Look at the actual ERROR rows + 'לא תקין' rows to see if there's a pattern."""
import sys
import openpyxl
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_filled.xlsx")
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

for i in range(5, len(rows)):
    row = rows[i]
    nohel = row[1]
    answer = row[5]
    verdict = row[9]
    if not (nohel and answer):
        continue
    v = str(verdict or "").strip()
    if v == "תקין":
        continue
    print(f"=== ROW {i} (נוהל={nohel}) — verdict: {v[:80]!r} ===")
    print(f"  שאלה:           {(str(row[4])[:100] if row[4] else '')!r}")
    print(f"  תשובה נכונה:    {(str(row[6])[:120] if row[6] else '')!r}")
    print(f"  תשובת המערכת:   {(str(answer)[:300])!r}")
    print()
