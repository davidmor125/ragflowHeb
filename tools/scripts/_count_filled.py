"""Count how many rows already have model answers in the filled Excel."""
import sys
import openpyxl
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_filled.xlsx")
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

filled = []
counts = {"תקין": 0, "חלקי": 0, "לא תקין": 0, "ERROR": 0, "other": 0}
for i in range(5, len(rows)):
    row = rows[i]
    nohel = row[1]
    answer = row[5]
    verdict = row[9]
    if nohel and answer:
        filled.append((i, nohel, verdict))
        v = str(verdict or "").strip()
        # verdict cell may have "verdict — reason" suffix
        v_main = v.split(" —")[0].strip() if v else ""
        if v_main in counts:
            counts[v_main] += 1
        elif v_main.startswith("ERROR"):
            counts["ERROR"] += 1
        else:
            counts["other"] += 1

print(f"rows filled so far: {len(filled)} / {sum(1 for r in rows[5:] if r[1])}")
print(f"verdicts: {counts}")
print()
print("first 5 and last 5 filled rows:")
for i, n, v in filled[:5] + filled[-5:]:
    print(f"  row {i:3d} (נוהל={n}): {(str(v)[:80] if v else '<no verdict>')!r}")
