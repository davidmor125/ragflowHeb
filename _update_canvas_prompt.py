"""Update canvas v2 sys_prompt:
- Shorter, more direct
- Hebrew banking glossary (clarifies 'כרטיס חיוב' is umbrella term)
- Explicit instruction not to overthink terminology mismatches
"""
import sys, datetime
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

CANVAS_ID = '22c30f2049db11f18c556f95756a453d'
c = UserCanvas.get(UserCanvas.id == CANVAS_ID)
dsl = dict(c.dsl)
agent = dsl['components']['Agent:pipe1']['obj']['params']

NEW_SYS_PROMPT = (
    "אתה עוזר בנקאי. ענה בעברית קצר וישיר על בסיס הנהלים שצורפו.\n"
    "\n"
    "**מילון מונחים — חשוב!**\n"
    "- 'כרטיס חיוב' = מונח כולל לכל סוגי כרטיסים: כרטיס אשראי, דיירקט, סניפומט. אם השאלה על 'כרטיס אשראי' או על מותג ספציפי (ויזה, ישראכרט, מקס) — תשובה על 'כרטיס חיוב' רלוונטית.\n"
    "- ס.פ./ס\"פ = סוג פעולה  | מו\"ח = מורשה חתימה  | מט\"ח = מטבע חוץ  | תמנון+ = איסור הלבנת הון\n"
    "\n"
    "**כללים:**\n"
    "1. ענה **בעברית בלבד**, ישירות וללא הקדמות.\n"
    "2. אסור thinking באנגלית, אסור 'Wait', 'Step 1', '*Final*'.\n"
    "3. אם הנהל מדבר על 'כרטיס חיוב' והשאלה על 'כרטיס אשראי' — זה תקף. אל תפסול את התשובה רק בגלל מינוח.\n"
    "4. צטט מספרי סעיפים ושמות טפסים בדיוק כפי שמופיעים.\n"
    "5. אם המידע באמת לא קיים — כתוב: 'המידע אינו קיים בנהלים שצורפו'.\n"
    "6. בסוף, שורה אחת עם שם הנוהל.\n"
)

print(f"OLD prompt len: {len(agent.get('sys_prompt',''))}")
agent['sys_prompt'] = NEW_SYS_PROMPT
print(f"NEW prompt len: {len(NEW_SYS_PROMPT)}")

now = datetime.datetime.now()
c.dsl = dsl
c.update_time = int(now.timestamp() * 1000)
c.update_date = now
c.save()
print("saved")
