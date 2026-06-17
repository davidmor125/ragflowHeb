import sys
sys.stdout.reconfigure(encoding='utf-8')
from common.text_utils import contains_hebrew, reorder_bidi

stored = """
יווק ףרג :גוס
2018 רבמצד דע 2009 רבמצד ,רצותב הדובעל הרומתה רועישו תויונפה תורשמה רועיש ,הלטבאה רועיש 1-'א רויא :תרתוכ
 :תויוותו םיריצ
(8 דע 0) םיזוחא :ילאמש Y ריצ
"""

print("=== STORED IN ES (what user sees) ===")
print(stored)
print()
print("=== contains_hebrew(stored)? ===")
print(contains_hebrew(stored))
print()
print("=== Apply reorder_bidi line by line ===")
fixed = "\n".join(reorder_bidi(line) or line for line in stored.split("\n"))
print(fixed)
print()
print("=== Apply reorder_bidi twice (would re-flip) ===")
fixed2 = "\n".join(reorder_bidi(line) or line for line in fixed.split("\n"))
print(fixed2)
