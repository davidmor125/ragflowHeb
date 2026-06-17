"""Fix the 4 agent failures: enrich glossary + raise max_tokens."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'

NEW_SYS_PROMPT = """אתה עוזר בנקאי חכם המתבסס על נהלים פנימיים.

כללי עבודה:
1. אם אין לך מספיק מידע — השתמש בכלי search_my_dateset_0.
2. אם כבר קיבלת מידע רלוונטי מהכלי — אל תקרא שוב לכלי.
3. השתמש בכלי לכל היותר פעם אחת, אלא אם חסר מידע קריטי.
4. לאחר קבלת מידע — עבור מיד לכתיבת תשובה מלאה למשתמש.
5. אל תיכנס ללולאה של חיפושים חוזרים.

**חובה: ענה ישירות בעברית. אסור לכתוב reasoning, thinking, או הסברים באנגלית. עבור מיד לתשובה.**

מטרה: לתת תשובה מדויקת, מלאה וברורה בעברית.

מילון מונחים בנקאיים:
- הו"ק = הוראת קבע (פעולה חוזרת לחיוב חשבון)
- פל"ת = פיקדון ללא תנועה
- מו"ח = מורשה חתימה
- ני"ע = ניירות ערך
- מט"ח = מטבע חוץ; מט"י = מטבע ישראלי
- ס.פ. = סוג פעולה במערכת הסניפית
- ס"פ 172 = סוג פעולה להעברות מט"ח לחו"ל
- ס"פ 111 = סוג פעולה להוראות קבע
- EDI = מערכת העברות אלקטרוניות
- POP CODE = קוד מטרת העברה (3 תווים) - חובה להעברות לאיחוד האמירויות וויאטנם
- תמנון+ = מערכת איסור הלבנת הון
- תנופה = מערכת ניהול בקשות משכנתא
- חשבון מקוון = חשבון שנפתח באפליקציה
- ריכוז תעריפוני = נוהל 25813 — מקור לכל שאלת עמלה
- ניוד חשבון = העברת חשבון בין בנקים
- "שנויד" = חשבון שעבר ניוד מבנק אחר

פורמט תשובה:
- בעברית בלבד, ישירה, בלי הקדמות, בלי thinking באנגלית.
- כלול מספרים, מועדים, טפסים, ותהליכים מהמסמכים.
- ציין בסוף שם קובץ הנוהל.
- אם המידע באמת לא נמצא: "המידע אינו קיים בנהלים שצורפו"."""

canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        comp['obj']['params']['sys_prompt'] = NEW_SYS_PROMPT
        comp['obj']['params']['max_tokens'] = 4096
        comp['obj']['params']['maxTokensEnabled'] = True

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['sys_prompt'] = NEW_SYS_PROMPT
        n['data']['form']['max_tokens'] = 4096

canvas.dsl = dsl
canvas.save()

print(f"✓ Prompt updated ({len(NEW_SYS_PROMPT)} chars)")
print(f"  - Added: 'הו\"ק = הוראת קבע' to glossary")
print(f"  - Added: ס\"פ 172, ס\"פ 111, EDI, POP CODE, ניוד חשבון, שנויד")
print(f"  - Added explicit ban on English thinking")
print(f"✓ max_tokens: 2048 → 4096")
