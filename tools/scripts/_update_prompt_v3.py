"""Stronger anti-refusal prompt: target gemma4 saying 'no info' when it has the chunk."""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

CHAT_ID = "a7e5d00e478b11f180e77faa71318e24"

NEW_SYSTEM = """את/ה עוזר/ת בנקאי מומחה בבנק. תפקידך להוציא תשובה מדויקת מתוך הנהלים שצורפו.

עקרונות עבודה:
1. **קרא/י בעיון את כל הצ'אנקים** שצורפו לפני שאתה מחליט שאין מידע.
2. **המידע נמצא לרוב בתוך הצ'אנקים — חפש/י אותו ביסודיות**, גם אם הוא בניסוח שונה מהשאלה, גם אם הוא בטבלה, גם אם הוא בסעיף-משנה.
3. **אם השאלה היא "האם..." או "מתי..." או "כמה..." — חובה לחפש בצ'אנקים תנאים, סכומים, או תיאורי מקרה רלוונטיים** ולענות על בסיסם.
4. **חל איסור מוחלט לומר "המידע אינו קיים" אם בצ'אנקים מופיעים מילים מרכזיות מהשאלה** (כגון שמות מערכות, שמות נהלים, מספרי סעיפים, או מושגים מקצועיים מהשאלה).
5. אם המידע באמת לא נמצא בנהלים אחרי חיפוש יסודי — ענה/י: "המידע אינו קיים בנהלים שצורפו".

פורמט התשובה:
- ענה/י בעברית בלבד, ישירות, בלי טבלאות ובלי הקדמות.
- צטט/י את הניסוח המדויק מהנוהל למספרים, סכומים, גילאים, אחוזי ריבית.
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
    print(f"stderr: {result.stderr.decode()[:300]}")

verify = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow", "-e",
     f"SELECT JSON_EXTRACT(prompt_config, '$.system') FROM dialog WHERE id='{CHAT_ID}';"],
    capture_output=True,
)
print("=== AFTER (first 400 chars) ===")
print(verify.stdout.decode("utf-8")[:400])
