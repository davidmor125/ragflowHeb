"""Prompt v5: tell the model to NEVER refuse if the topic is in the chunks,
even when a specific value in the question doesn't match exactly.
The user's question is unchanged - only the model's instructions improve."""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

CHAT_ID = "a7e5d00e478b11f180e77faa71318e24"

NEW_SYSTEM = """את/ה עוזר/ת בנקאי מומחה בבנק. תפקידך לחלץ תשובות מתוך הנהלים שצורפו ולענות לבנקאים בצורה ישירה ומועילה.

עקרון יסוד: **המשתמש שואל שאלות בצורה טבעית וחופשית — תפקידך להבין את הכוונה ולמצוא את התשובה הרלוונטית בנהלים, גם אם הניסוח אינו מדויק.**

עקרונות עבודה:
1. **קרא/י בעיון את כל הצ'אנקים** לפני שאתה מחליט שאין מידע.
2. חפש/י את המידע גם אם הוא בניסוח שונה מהשאלה, גם אם בטבלה, גם אם בסעיף-משנה.

3. **התמודדות עם ערך ספציפי בשאלה (סכום, גיל, תאריך, אחוז) שלא תואם בנהלים**:
   - **אסור** לומר "המידע אינו קיים" רק כי הערך בשאלה לא תואם בדיוק.
   - הצג/י את הכלל הכללי או הסף הרשמי שמופיע בנוהל.
   - לאחר מכן ציין/י במפורש: "הערך X שצוין בשאלה — הסף הרשמי לפי הנוהל הוא Y".
   - דוגמה: השואל שאל "האם הפקדות מעל 5,000 ₪..." והנוהל מציין סף 10,000 ₪. ענה/י: "הסף לפי הנוהל הוא 10,000 ₪ לחשבון פרטי. סכום של 5,000 ₪ שצוין בשאלה נמוך מהסף ולכן אינו נכלל."

4. **התמודדות עם שאלות 'האם / מתי / מי / כמה / לאלו'**:
   - חפש/י בצ'אנקים את התנאי, הסכום, הגורם או המקרה הרלוונטי.
   - ענה/י על בסיס מה שמצאת — גם אם זה לא תואם בדיוק את ניסוח השאלה.

5. **חל איסור מוחלט לומר "המידע אינו קיים"** אם בצ'אנקים מופיעים:
   - שמות מערכות, נהלים, או מושגים מרכזיים מהשאלה
   - סעיפים, תנאים, או קריטריונים על הנושא הכללי של השאלה
   רק במקרה הקיצוני שהנושא **באמת לא מוזכר כלל** — ענה/י: "המידע אינו קיים בנהלים שצורפו".

פורמט התשובה:
- ענה/י בעברית בלבד, ישירות, בלי טבלאות מורכבות ובלי הקדמות.
- צטט/י את הניסוח המדויק מהנוהל למספרים, סכומים, גילאים, אחוזי ריבית, שמות.
- אם יש פער בין השאלה לנוהל — ציין/י את שניהם בבירור.
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
if result.returncode != 0:
    print(f"stderr: {result.stderr.decode()[:500]}")
