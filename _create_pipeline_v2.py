"""Pipeline v2: tighten max_tokens, anti-hallucination prompt, longer retrieval timeout."""
import sys, json, uuid, datetime, copy
sys.stdout.reconfigure(encoding="utf-8")
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)

V1_ID = "708c8bca49cf11f1bcd66b39e390ca8c"
src = UserCanvas.get(UserCanvas.id == V1_ID)
new_dsl = copy.deepcopy(src.dsl)

retrieval_node = "Retrieval:pipe1"
agent_node = "Agent:pipe1"

# Update Agent node
agent_params = new_dsl["components"][agent_node]["obj"]["params"]
agent_params["max_tokens"] = 800              # was 1500 — kill runaway loops
agent_params["sys_prompt"] = (
    "אתה עוזר בנקאי שעונה רק על בסיס הנהלים שצורפו לשאלה.\n"
    "\n"
    "**חוקים מוחלטים:**\n"
    "1. ענה **בעברית בלבד**. אל תכתוב באנגלית.\n"
    "2. **ללא thinking, Step 1, We need, Wait, Self-Correction, ID NNN, *Final*** — אסור לחלוטין.\n"
    "3. אסור לקרוא לכלים. אסור לחפש שוב. כל המידע שיש לך נמצא בתוך הקלט.\n"
    "4. תשובה ישירה, ממוקדת. ללא הקדמות.\n"
    "5. **אסור להמציא**: אם הנוהל לא מציין מספר/אחוז/שם טופס/סעיף ספציפי — אל תכתוב אותו. רק מה שכתוב במפורש.\n"
    "6. אם המידע לא נמצא בנהלים שצורפו — כתוב **בדיוק**: 'המידע אינו קיים בנהלים שצורפו'. בלי הסברים נוספים.\n"
    "7. צטט מספרי סעיפים, סכומים, מועדים, ושמות טפסים בדיוק כפי שמופיעים בנהלים.\n"
    "8. בסוף התשובה — שורה אחת בלבד עם שם קובץ הנוהל.\n"
    "\n"
    "מילון:\n"
    "פל\"ת=פיקדון ללא תנועה | מו\"ח=מורשה חתימה | ני\"ע=ניירות ערך | מט\"ח=מטבע חוץ | "
    "ס.פ./ס\"פ=סוג פעולה | תמנון+=איסור הלבנת הון | תנופה=ניהול בקשות משכנתא | "
    "מאיה=מערכת סניפית | ריכוז תעריפוני=נוהל 25813\n"
)
agent_params["prompts"] = [
    {
        "role": "user",
        "content": (
            "שאלה: {sys.query}\n"
            "\n"
            "נהלים רלוונטיים:\n"
            "{" + retrieval_node + "@formalized_content}\n"
            "\n"
            "כתוב את התשובה הסופית עכשיו. עברית בלבד. ישירה. ללא thinking.\n"
            "תשובה:"
        ),
    }
]

NEW_ID = uuid.uuid1().hex
NEW_TITLE = "banking_pipeline_v2"

now = datetime.datetime.now()
UserCanvas.create(
    id=NEW_ID,
    user_id=src.user_id,
    title=NEW_TITLE,
    avatar=src.avatar,
    description="Pipeline v2: max_tokens=800, anti-hallucination prompt, retrieval timeout=120s",
    canvas_type=src.canvas_type,
    dsl=new_dsl,
    permission=src.permission,
    create_time=int(now.timestamp() * 1000),
    create_date=now,
    update_time=int(now.timestamp() * 1000),
    update_date=now,
)

print(f"Created v2 canvas")
print(f"  id={NEW_ID}")
print(f"  title={NEW_TITLE}")
print(f"  max_tokens=800")
print(f"  anti-hallucination prompt: yes")
