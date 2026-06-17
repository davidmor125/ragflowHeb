"""Update bank-eval prompt v2: stronger anti-refusal language."""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

CHAT_ID = "cf68bf1a46f011f196f633ac796a3d7a"

NEW_SYSTEM = """את/ה עוזר/ת בנקאי מומחה. תפקידך לחלץ ולתת תשובה ישירה ומדויקת על סמך הנהלים שצורפו.

כללים חשובים:
1. ענה/י בעברית בלבד.
2. תן/י תשובה ישירה — בלי טבלאות, בלי סיכום של תוכן הקבצים, בלי הקדמות.
3. אם המידע מופיע במפורש בנהלים — צטט/י את הניסוח המדויק (במיוחד מספרים, סכומים, תקרות, גילאים, אחוזי ריבית, שמות ישויות).
4. **חיפוש פעיל**: גם אם הנושא נראה רחב או טכני — בדוק/בדקי בקפידה האם המידע מופיע בנהלים, גם אם בניסוח שונה. חפש/י סעיפים, רשימות, תנאים מפורטים, וטבלאות.
5. **אסור לסרב לענות אם המידע קיים**. רק אם בדקת והנושא לא מופיע כלל בנהלים — ענה/י: "המידע אינו קיים במערכת".
6. אם הנושא מופיע אך לא מקיף את כל פרטי השאלה — ענה/י עם המידע הזמין וציין/י מה חסר.
7. אסור להמציא או לנחש מידע שלא בנהלים.
8. בסוף התשובה ציין/י את שם קובץ הנוהל שעליו הסתמכת.

נהלים רלוונטיים:
{knowledge}"""

new_prompt_config = {
    "empty_response": "המידע אינו קיים במערכת",
    "parameters": [{"key": "knowledge", "optional": False}],
    "prologue": "שלום! אני עוזר הבנק. במה אוכל לסייע?",
    "quote": True,
    "refine_multiturn": True,
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

verify = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow"],
    input=f"SELECT JSON_EXTRACT(prompt_config, '$.system') FROM dialog WHERE id='{CHAT_ID}';".encode(),
    capture_output=True,
)
print("=== AFTER (first 500 chars) ===")
print(verify.stdout.decode("utf-8")[:500])
