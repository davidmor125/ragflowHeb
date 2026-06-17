"""Fix Query Rewriter — preserve original, only enrich."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

AGENT_ID = '08690e36494f11f1abe3f75f35493e6a'

NEW_REWRITER_PROMPT = """אתה מסייע למערכת חיפוש בנהלי בנק. תפקידך להעשיר שאילתת חיפוש — **לא לשכתב אותה**.

חוקים מחייבים:
1. **השאלה המקורית של המשתמש חייבת להופיע במלואה** בפלט.
2. אם השאלה מנוסחת היטב (יש בה מונחים בנקאיים ספציפיים) — **תחזיר אותה כפי שהיא, ללא שינוי**.
3. אם השאלה כללית מאוד או מכילה ראשי תיבות — הוסף **בסוגריים** את הפירוש המורחב.
4. הוסף **מילים נרדפות** רק אם השאלה כללית מדי, וכלול אותן אחרי השאלה המקורית.
5. תפלט **שורה אחת בלבד**, בלי הסברים.

מילון ראשי תיבות (להרחבה רק כשנדרש):
פל"ת = פיקדון ללא תנועה | מו"ח = מורשה חתימה | ני"ע = ניירות ערך | מט"ח = מטבע חוץ | ס.פ./ס"פ = סוג פעולה | תמנון+ = איסור הלבנת הון | תנופה = ניהול בקשות משכנתא | מאיה = מערכת סניפית | דולב = מערכת דוחות | ריכוז תעריפוני = נוהל 25813

דוגמאות:
שאלה: "איך עושים העברת מט\"ח לאיחוד האמירויות"
פלט: איך עושים העברת מט"ח לאיחוד האמירויות

שאלה: "מה ההגדרה לחשבון CB?"
פלט: מה ההגדרה לחשבון CB? (חשבון בעלי זיקה לחו"ל)

שאלה: "איך מבטלים?"
פלט: איך מבטלים? (ביטול שירות / כרטיס / הוראה)
"""

c = UserCanvas.get(UserCanvas.id == AGENT_ID)
dsl = json.loads(json.dumps(c.dsl))

# Find Rewriter and Retrieval
for cid, comp in dsl['components'].items():
    cn = comp['obj']['component_name']
    if cn == 'Agent' and 'Rewriter' in str(comp.get('obj', {}).get('params', {}).get('sys_prompt', ''))[:50]:
        comp['obj']['params']['sys_prompt'] = NEW_REWRITER_PROMPT
        print(f"✓ Updated Query_Rewriter prompt (preserves original)")
    elif cn == 'Retrieval':
        comp['obj']['params']['similarity_threshold'] = 0.0
        comp['obj']['params']['top_n'] = 15
        print(f"✓ Retrieval: similarity_threshold=0.0, top_n=15")

# Mirror in graph nodes
for n in dsl.get('graph', {}).get('nodes', []):
    label = n.get('data', {}).get('label', '')
    name = n.get('data', {}).get('name', '')
    if label == 'Agent' and 'Rewriter' in name:
        n['data']['form']['sys_prompt'] = NEW_REWRITER_PROMPT
    elif label == 'Retrieval':
        n['data']['form']['similarity_threshold'] = 0.0
        n['data']['form']['top_n'] = 15

c.dsl = dsl
c.save()
print("\nSaved.")
