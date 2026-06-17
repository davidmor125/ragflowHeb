"""3 improvements for Hebrew RAG quality:
1. Translate the Retrieval tool description to Hebrew (so the LLM
   reasons about WHEN to call it in the same language as the question)
2. Strengthen the system prompt's Hebrew-only enforcement
3. Seed a Hebrew banking glossary for hozrim_poc."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas, Knowledgebase
DB.connect(reuse_if_open=True)
# Note: GlossaryTermService not present in this container build.
# We embed the glossary directly in the system prompt instead.

AGENT_ID = '54e45b8048a011f18e412992204f7aa3'   # banking_agentic_rag
KB_ID    = '928f816a487a11f1a37a31aeaf1accf8'   # hozrim_poc
kb       = Knowledgebase.get(Knowledgebase.id == KB_ID)

# ============================================================
# 1+2. Update Agent canvas: Hebrew tool description + stronger prompt
# ============================================================
canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(canvas.dsl))  # deep copy

NEW_TOOL_DESC = (
    "חיפוש במאגר נהלי הבנק. הכלי מקבל שאילתת חיפוש בעברית ומחזיר את "
    "הצ'אנקים הרלוונטיים מהנהלים. **השתמש בכלי לכל שאלה בנקאית** — "
    "ענה רק על בסיס מה שהוחזר. אם התשובה הראשונה לא מספקת, קרא לכלי שוב "
    "עם ניסוח חלופי (לדוגמה: הוסף את שם המערכת הספציפית, השתמש "
    "בראשי תיבות בנקאיים, או חפש לפי נושא רחב יותר)."
)

GLOSSARY_BLOCK = """## מילון מונחים בנקאיים
- פל"ת = פיקדון ללא תנועה (חשבון בלי פעילות 11+ חודשים)
- מו"ח = מורשה חתימה
- ני"ע = ניירות ערך (מניות, אגרות חוב)
- מט"ח = מטבע חוץ; מט"י = מטבע ישראלי (₪)
- ס.פ. = סוג פעולה במערכת הסניפית (לדוגמה ס.פ. 940 — הזמנת פנקסי שיקים)
- גלא"ש = גורם לאישור אשראי שיורי
- תמנון+ = מערכת איסור הלבנת הון
- תנופה = מערכת ניהול בקשות משכנתא
- דולב = מערכת דוחות הבנק
- מאיה = מערכת סניפית מרכזית
- סניפומט = מכשיר אוטומטי בסניף
- מת"ף = מערכת תיוק פניות
- כא"ש = כניסה לאשראי שיורי (כא"ש 8 = טופס מס' 8)
- חשבון מקוון = חשבון שנפתח דרך אפליקציית הבנק (תקרת תקבולים 50,000 ₪/חודש, מזומן עד 5,000 ₪/חודש)
- POP CODE = קוד מטרת העברה לאיחוד האמירויות וויאטנם
- ריכוז תעריפוני = נוהל 25813 — מקור לכל שאלת עמלה
- ניוד חשבון = העברת חשבון בין בנקים"""

NEW_SYS_PROMPT = f"""# תפקיד
אתה עוזר בנקאי מומחה. תפקידך לענות על שאלות בנקאיות על בסיס נהלים פנימיים שבמאגר.

# כללי עבודה — חובה
1. **תמיד עברית.** התשובה, ההסבר, וכל ה-reasoning הפנימי שלך — בעברית בלבד.
2. **תמיד השתמש בכלי `Retrieval`** למציאת מידע, לפני שאתה עונה. אסור לענות מהזיכרון.
3. אם הצ'אנקים שאוחזרו לא ענו על השאלה — קרא ל-`Retrieval` **שוב** עם ניסוח אחר.
4. ענה **רק על בסיס מה שאוחזר**. אסור להמציא או להוסיף מידע.

{GLOSSARY_BLOCK}

# טיפים לאחזור איכותי
- אם השאלה מכילה מונח כללי כמו "חשבון מקוון", הוסף הקשר ספציפי לשאילתה (לדוגמה: "תנאי הפקדה בחשבון מקוון יחיד" במקום רק "חשבון מקוון").
- אם השאלה היא על עמלה ולא נמצא מידע — נסה "ריכוז תעריפוני" או "עלות שירות".
- אם השאלה מזכירה מערכת ספציפית — כלול את שם המערכת בשאילתה.
- ראשי תיבות בנקאיים — השאר אותם בדיוק כפי שהם בשאלה.
- מקסימום 3 ניסיונות אחזור לשאלה אחת.

# פורמט תשובה
- תשובה ישירה, בלי הקדמות, בעברית.
- צטט מספרים, סכומים, אחוזי ריבית, וגילאים **בדיוק** כפי שמופיעים בנוהל.
- שמור על ראשי תיבות וניסוח עברי מקצועי.
- ציין בסוף: שם הנוהל / קובץ המקור.
- אם אחרי 3 ניסיונות לא מצאת תשובה ברורה: "המידע אינו קיים בנהלים שצורפו"."""

# Patch the components dict
for cid, comp in dsl['components'].items():
    if comp['obj']['component_name'] == 'Agent':
        comp['obj']['params']['sys_prompt'] = NEW_SYS_PROMPT
        for tool in comp['obj']['params'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['description'] = NEW_TOOL_DESC

# Patch the graph nodes too (so the UI shows the same)
for n in dsl.get('graph', {}).get('nodes', []):
    if n.get('data', {}).get('label') == 'Agent':
        n['data']['form']['sys_prompt'] = NEW_SYS_PROMPT
        for tool in n['data']['form'].get('tools', []):
            if tool.get('component_name') == 'Retrieval':
                tool['params']['description'] = NEW_TOOL_DESC

canvas.dsl = dsl
canvas.save()
print("✓ Agent canvas updated:")
print(f"  - System prompt: {len(NEW_SYS_PROMPT)} chars (Hebrew)")
print(f"  - Tool description: {len(NEW_TOOL_DESC)} chars (Hebrew)")

print(f"  Glossary embedded inline ({len(GLOSSARY_BLOCK)} chars, 17 terms)")
import sys as _sys
_sys.exit(0)

# (Kept below for reference — would seed via service if available)
GLOSSARY_UNUSED = [
    {"term": 'פל"ת', "full_form": "פיקדון ללא תנועה",
     "definition": "חשבון או פיקדון שלא הייתה בו פעילות במשך 11 חודשים ומעלה.",
     "aliases": ["פלת", "פל\"ת", "פיקדון ללא תנועה"]},

    {"term": 'מו"ח', "full_form": "מורשה חתימה",
     "definition": "אדם שהוסמך לחתום בשם הבנק על מסמכים מסוימים, נדרש לאישור פעולות מסוימות.",
     "aliases": ["מו\"ח", "מוח", "מורשה חתימה"]},

    {"term": 'ני"ע', "full_form": "ניירות ערך",
     "definition": "מניות, אגרות חוב, וקרנות סל הנסחרות בבורסה.",
     "aliases": ["ניע", "ניירות ערך"]},

    {"term": 'מט"ח', "full_form": "מטבע חוץ",
     "definition": "מטבע זר שאינו שקל ישראלי (דולר, אירו, פאונד וכו').",
     "aliases": ["מטח", "מט\"ח"]},

    {"term": 'מט"י', "full_form": "מטבע ישראלי",
     "definition": "שקל חדש (₪).",
     "aliases": ["מטי", "מט\"י"]},

    {"term": 'ס.פ.', "full_form": "סוג פעולה",
     "definition": "קוד פעולה במערכת הסניפית (לדוגמה ס.פ. 940 — הזמנת פנקסי שיקים, ס.פ. 501 — ביטול כרטיס).",
     "aliases": ["סוג פעולה", "ס\"פ", "ספ"]},

    {"term": 'גלא"ש', "full_form": "גורם לאישור אשראי שיורי",
     "definition": "גורם בכיר בחטיבת האשראי שמאשר בקשות הלוואה מורכבות.",
     "aliases": ["גלאש", "גלא\"ש"]},

    {"term": 'תמנון+', "full_form": "מערכת איסור הלבנת הון",
     "definition": "מערכת לדיווח על פעולות בלתי רגילות לרשות לאיסור הלבנת הון.",
     "aliases": ["תמנון", "תמנון פלוס", "תמנון+"]},

    {"term": "תנופה", "full_form": "מערכת לניהול בקשות משכנתא",
     "definition": "מערכת CRM של הבנק לניהול תהליך הגשת בקשת משכנתא ואישורה.",
     "aliases": []},

    {"term": "דולב", "full_form": "מערכת דוחות הבנק",
     "definition": "מערכת המציגה דוחות יומיים אוטומטיים לסניפים.",
     "aliases": []},

    {"term": "סניפומט", "full_form": "מכשיר אוטומטי בסניף",
     "definition": "מכשיר עצמאי בסניף לביצוע פעולות בסיסיות (משיכה, הפקדה, מאזן).",
     "aliases": ["סניפומט EMV"]},

    {"term": "מאיה", "full_form": "מערכת סניפית",
     "definition": "מערכת המחשוב המרכזית של הסניף לתפעול חשבונות.",
     "aliases": ["מערכת מאיה"]},

    {"term": 'מת"ף', "full_form": "מערכת תיוק פניות",
     "definition": "מערכת לתיעוד פניות לקוחות והעברתן בין יחידות.",
     "aliases": ["מתף", "מת\"ף"]},

    {"term": "מקוון", "full_form": "חשבון מקוון",
     "definition": "חשבון שנפתח דרך אפליקציית הבנק, עם מגבלות פעילות שונות מחשבון רגיל (סך תקבולים עד 50,000 ₪/חודש, הפקדת מזומן עד 5,000 ₪/חודש וכו').",
     "aliases": ["חשבון מקוון", "מקוון יחיד", "מקוון משותף", "מקוון נוער"]},

    {"term": 'הכר את הלקוח', "full_form": "שאלון KYC",
     "definition": "שאלון חובה הנערך עם הלקוח בעת פתיחת חשבון ומעודכן בשינויי מצב.",
     "aliases": ["הכר את הלקוח", "KYC"]},

    {"term": "פנקסי המחאות", "full_form": "פנקסי שיקים",
     "definition": "פנקס שיקים מודפס. לקוח חדש יכול להזמין עד 3 פנקסים ב-3 החודשים הראשונים.",
     "aliases": ["פנקסי שיקים", "פנקס המחאות"]},

    {"term": "POP CODE", "full_form": "Purpose of Payment Code",
     "definition": "קוד 3 תווים המתאר את מטרת ההעברה במט\"ח, נדרש להעברות לאיחוד האמירויות וויאטנם.",
     "aliases": ["POP", "פופ קוד"]},

    {"term": "ריכוז תעריפוני", "full_form": "ריכוז תעריפוני כל הבנקים בקבוצה",
     "definition": "נוהל מס' 25813 — מאגד את כל העמלות והתעריפים של בנקי הקבוצה. כשנשאלת על עמלה, ההפניה היא לנוהל זה.",
     "aliases": ["תעריפון", "נוהל 25813"]},

    {"term": 'כא"ש', "full_form": "כניסה לאשראי שיורי",
     "definition": "טופס לפתיחת בקשת אשראי שיורי ללקוח (כא\"ש 8 = טופס מס' 8).",
     "aliases": ["כאש", "כא\"ש 8"]},

    {"term": "ניוד חשבון", "full_form": "העברת חשבון בין בנקים",
     "definition": "תהליך מוסדר להעברת חשבון מבנק אחר לבנק הזה (או להפך), כולל העברת הוראות קבע, ניירות ערך, ופעילות שוטפת.",
     "aliases": ["ניוד", "העברת חשבון"]},
]

result = GlossaryTermService.upsert_many(
    kb_id=KB_ID,
    tenant_id=kb.tenant_id,
    created_by=kb.created_by,
    rows=GLOSSARY,
)
print(f"\n✓ Glossary seeded for hozrim_poc:")
print(f"  inserted: {result['inserted']}")
print(f"  updated:  {result['updated']}")
print(f"  total terms: {len(GLOSSARY)}")

# Show the rendered glossary that will be injected into the LLM prompt
rendered = GlossaryTermService.render_for_prompt(KB_ID)
print(f"\n  Rendered for prompt ({len(rendered)} chars):")
print('  ---')
for line in rendered.split('\n')[:5]:
    print(f"  {line}")
print(f"  ... ({len(rendered.split(chr(10)))-5} more lines)")
