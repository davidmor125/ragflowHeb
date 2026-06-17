import sys
sys.stdout.reconfigure(encoding='utf-8')
from common.text_utils import contains_hebrew, reorder_bidi

# What Gemma 4 cloud actually returned with the new English-labels prompt
gemma_output = """Type: line chart
Title: 2018-2024 לארשי קנב תיביר
Axes and labels: none
Legend: none
Data: רשימת שנים ואחוזים:
2018: 0.1% ראוני
2020: 0.1% גרמ
2022: 0.35% לירפא
2023: 3.75% ראוני
2024: 4.5% ראוני
Notes and source: רוקמ: לארשי קנב"""

STRUCTURE_LABELS = (
    "Type:", "Title:", "Axes and labels:", "Legend:", "Data:",
    "Notes and source:",
)

def fix_hebrew_line(line):
    if not contains_hebrew(line):
        return line
    for label in STRUCTURE_LABELS:
        if line.lstrip().startswith(label):
            prefix, _, value = line.partition(":")
            fixed_value = reorder_bidi(value) or value
            return f"{prefix}:{fixed_value}"
    return reorder_bidi(line) or line

print("=== INPUT (raw from Gemma) ===")
print(gemma_output)
print()
print("=== OUTPUT (after smart fix) ===")
print("\n".join(fix_hebrew_line(line) for line in gemma_output.split("\n")))
