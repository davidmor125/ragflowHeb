"""Clear cols 5+9 for rows 8-11 (1-based) so re-run with --skip-filled redoes them."""
import sys
import openpyxl
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:/develop/html_output/_eval_report/newtest/test_report_24_05_filled.xlsx")
wb = openpyxl.load_workbook(p)
ws = wb.active

# Drop images so save doesn't crash on the bank logo.
for s in wb.worksheets:
    if hasattr(s, "_images"):
        s._images = []

# 1-based rows 8 through 11 (Excel) — i.e. 0-based 7-10. The script uses
# 0-based COL_MODEL_ANSWER=5, COL_VERDICT=9; openpyxl is 1-based so +1.
for excel_row in [8, 9, 10, 11]:
    ws.cell(row=excel_row + 1, column=5 + 1).value = None  # +1: header row 5 in 0-based -> row 6 1-based; but our data starts at openpyxl row 6
# Wait — recheck: rows[5] in openpyxl (1-based) = excel display row 6.
# In the Excel shown to user, rows are: header=row 5, first data=row 6.
# But our _inspect_filled.py used rows[5]..rows[8] (0-based list), which in
# openpyxl 1-based = rows 6..9. The "ROW 8" in inspect output = openpyxl row 9.
# So to clear inspect's rows 8-11 we need openpyxl rows 9-12.

# Reset and do it correctly:
for excel_row_1based in [9, 10, 11, 12]:
    ws.cell(row=excel_row_1based, column=6).value = None  # col 5 (0-based) = col 6 (1-based) = תשובת המערכת
    ws.cell(row=excel_row_1based, column=10).value = None  # col 9 (0-based) = col 10 (1-based) = verdict

wb.save(p)
print(f"cleared cols F (תשובת המערכת) and J (verdict) for openpyxl rows 9-12")
