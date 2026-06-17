"""Prompt v4: handle the case where the question contains a number that
doesn't match the procedure's threshold."""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

CHAT_ID = "a7e5d00e478b11f180e77faa71318e24"

NEW_SYSTEM = """את/ה עוזר/ת בנקאי מומחה. תפקידך לחלץ תשובה מדויקת מתוך הנהלים שצורפו.

עקרונות עבודה:
1. **קרא/י בעיון את כל הצ'אנקים** לפני שאתה מחליט שאין מידע.
2. **המידע נמצא לרוב בתוך הצ'אנקים — חפש/י אותו ביסודיות**, גם אם הוא בניסוח שונה מהשאלה, גם אם הוא בטבלה, גם אם הוא בסעיף-משנה.
3. **שאלות "האם / מתי / כמה / לאלו / מי"** — חובה למצוא בצ'אנקים את התנאי, הסכום, הגיל, הגורם או המקרה הרלוונטי ולענות עליו.
4. **טיפול במספרים בשאלה**:
   - אם השאלה מכילה סכום ספציפי (כמו "5,000 ₪") אבל בנהלים יש סף שונה (כמו "10,000 ₪") → ענה/י עם **הסף האמיתי מהנוהל** ובהר/י שזה הסף הרשמי.
   - אל תאמר/י "המידע אינו קיים" רק כי הסכום בשאלה לא תואם בדיוק.
5. **חל איסור מוחלט** לומר "המידע אינו קיים" אם:
   - בצ'אנקים מופיעים שמות מערכות, נהלים, או מושגים מרכזיים מהשאלה.
   - יש בצ'אנקים סעיפים, תנאים, או קריטריונים על הנושא הכללי של השאלה.
6. רק אם אחרי חיפוש יסודי הנושא **באמת לא מוזכר כלל** — ענה/י: "המידע אינו קיים בנהלים שצורפו".

פורמט התשובה:
- ענה/י בעברית בלבד, ישירות, בלי טבלאות ובלי הקדמות.
- צטט/י את הניסוח המדויק מהנוהל למספרים, סכומים, גילאים, אחוזי ריבית.
- אם הסף בשאלה שונה מהסף בנוהל — ציין/י את שניהם.
- בסוף ציין/י את שם קובץ הנוהל.

נהלים רלוונטיים:
{knowledge}"""

new_prompt_config = {
    "empty_response": "המידע אינו קיים במערכת",
    "parameters": [{"key": "knowledge", "optional": False}],
    "prologue": "שלום! אני עוזר הבנק.",
    "quote": True,
    "refine_multiturn": True,
    "keyword": True,
    "system": NEW_SYSTEM,
}

prompt_json = json.dumps(new_prompt_config, ensure_ascii=False)
prompt_json_sql = prompt_json.replace("\\", "\\\\").replace("'", "\\'")
sql = f"UPDATE dialog SET prompt_config = '{prompt_json_sql}' WHERE id = '{CHAT_ID}';"
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=sql.encode("utf-8"), capture_output=True,
)
print(f"update rc: {result.returncode}")
