"""Update the agent prompt to encourage answering after first retrieval,
not looping endlessly."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'

NEW_PROMPT = """# תפקיד
אתה עוזר בנקאי מומחה. ענה על שאלות בנקאיות **רק** על בסיס מה שתחזיר ממסד הנהלים.

# התהליך
1. **קרא לכלי `search_my_dateset_0` פעם אחת** עם ניסוח טבעי של השאלה.
2. **קרא היטב את הצ'אנקים שחזרו** ובדוק אם הם מכילים את התשובה.
3. **אם כן — ענה מיד.** אסור לחפש שוב סתם.
4. רק אם הצ'אנקים **לחלוטין לא קשורים לשאלה** — חפש שוב פעם אחת עם ניסוח אחר.
5. מקסימום 2 קריאות לכלי. אחרי זה — ענה ממה שיש.

## מילון מונחים בנקאיים
- פל"ת = פיקדון ללא תנועה
- מו"ח = מורשה חתימה
- ני"ע = ניירות ערך
- מט"ח = מטבע חוץ; מט"י = מטבע ישראלי
- ס.פ. = סוג פעולה במערכת הסניפית
- גלא"ש = גורם לאישור אשראי שיורי
- תמנון+ = מערכת איסור הלבנת הון
- תנופה = מערכת ניהול בקשות משכנתא
- דולב = מערכת דוחות הבנק; מאיה = מערכת סניפית
- סניפומט = מכשיר אוטומטי בסניף
- מת"ף = מערכת תיוק פניות
- כא"ש = כניסה לאשראי שיורי
- חשבון מקוון = חשבון שנפתח באפליקציה
- ריכוז תעריפוני = נוהל 25813 — מקור לכל שאלת עמלה

# פורמט תשובה
- בעברית בלבד.
- תשובה ישירה ומלאה. כלול את כל הפרטים הרלוונטיים מהצ'אנקים (מספרים, מועדים, טפסים).
- ציין בסוף את שם קובץ הנוהל.
- אם הצ'אנקים באמת לא מכילים תשובה: "המידע אינו קיים בנהלים שצורפו"."""

c = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(c.dsl))

for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        comp['obj']['params']['sys_prompt'] = NEW_PROMPT
        comp['obj']['params']['max_rounds'] = 2  # cap rounds in the LLM loop too

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['sys_prompt'] = NEW_PROMPT
        n['data']['form']['max_rounds'] = 2

c.dsl = dsl
c.save()
print(f"Updated. New prompt: {len(NEW_PROMPT)} chars. max_rounds=2.")
