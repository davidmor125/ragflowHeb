"""Fix the agent system prompt to reference the actual tool name
(`search_my_dateset_0`) instead of the canvas-component label "Retrieval"."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))

# Switch back to gemma4 — the user has confirmed it's the model they want
NEW_LLM = 'gemma4:31b-cloud@Ollama'

# The tool the LLM actually sees is "search_my_dateset_0" (with the typo + index suffix
# that RAGFlow appends in agent_with_tools.py). Don't use the UI label "Retrieval".
GLOSSARY = """## מילון מונחים בנקאיים
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
- חשבון מקוון = חשבון שנפתח באפליקציה (תקבולים עד 50,000 ₪/חודש)
- POP CODE = קוד מטרת העברת מט"ח
- ריכוז תעריפוני = נוהל 25813 — מקור לכל שאלת עמלה"""

NEW_SYS = f"""# תפקיד
אתה עוזר בנקאי מומחה. תפקידך לענות על שאלות בנקאיות **רק** על בסיס נהלים פנימיים שאתה מאחזר באמצעות הכלי שיש לך.

# כלל חובה — חיפוש לפני תשובה
**לכל שאלה — אסור לענות לפני שביצעת קריאה לכלי החיפוש.** הכלי הזמין לך נקרא `search_my_dateset_0` (זאת הקריאה שלך אל מסד הנהלים של הבנק).
- אם תענה בלי לקרוא לכלי — התשובה שגויה.
- אם הצ'אנקים שאוחזרו לא ענו על השאלה — קרא לכלי **שוב** עם ניסוח חלופי. עד 3 פעמים.

{GLOSSARY}

# טיפים לאחזור איכותי
- מונח כללי כמו "חשבון מקוון" — הוסף הקשר ספציפי בשאילתה (למשל "תנאי הפקדה בחשבון מקוון יחיד").
- שאלת עמלה ולא נמצא — חפש "ריכוז תעריפוני" או "עלות שירות".
- שאלה על מערכת — כלול את שמה (תמנון, תנופה, דולב, מאיה).

# פורמט תשובה
- בעברית בלבד.
- ישירה, בלי הקדמות.
- מספרים וסכומים בדיוק כפי שבנוהל.
- ציין בסוף את שם קובץ הנוהל.
- אם לא נמצא: "המידע אינו קיים בנהלים שצורפו"."""

NEW_TOOL_DESC = (
    "חפש במאגר נהלי הבנק. קלט: שאילתה בעברית. פלט: צ'אנקים רלוונטיים מהנהלים. "
    "השתמש לכל שאלה בנקאית. אם התוצאה הראשונה לא מספקת — קרא שוב עם ניסוח חלופי."
)

# Patch the components
for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        comp['obj']['params']['sys_prompt'] = NEW_SYS
        comp['obj']['params']['llm_id'] = NEW_LLM
        for tool in comp['obj']['params'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['description'] = NEW_TOOL_DESC

for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['sys_prompt'] = NEW_SYS
        n['data']['form']['llm_id'] = NEW_LLM
        for tool in n['data']['form'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['description'] = NEW_TOOL_DESC

canvas.dsl = dsl
canvas.save()
print("Updated:")
print(f"  llm: {NEW_LLM}")
print(f"  sys_prompt: {len(NEW_SYS)} chars (now references 'search_my_dateset_0')")
print(f"  tool description: {len(NEW_TOOL_DESC)} chars")
