"""Print the unique נוהל files referenced by the first 10 data rows of the
test Excel."""
import sys, openpyxl
sys.stdout.reconfigure(encoding="utf-8")

wb = openpyxl.load_workbook(
    r"C:/develop/html_output/_eval_report/newtest/test_report_24_05.xlsx",
    read_only=True, data_only=True,
)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

# rows[5] is first data row (1-based row 6 in Excel)
nohels = []
for i in range(5, len(rows)):
    n = rows[i][1]
    q = rows[i][4]
    if n and q:
        nohels.append(str(n).strip())
        if len(nohels) >= 10:
            break

unique = []
for n in nohels:
    if n not in unique:
        unique.append(n)
print("first 10 questions touch these נוהל files:")
print(",".join(nohels))
print()
print(f"unique ({len(unique)}):", unique)
