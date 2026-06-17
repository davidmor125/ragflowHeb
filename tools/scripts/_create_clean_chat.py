"""Create a fresh chat assistant 'bank-eval-clean' bound to test_five_files KB.
Same Hebrew prompt + reranker as bank-eval, but pointing to the small KB
to test if file dilution was the cause of the verdict drops."""

import sys, json, urllib.request, subprocess
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
NEW_KB_ID = "055ff3d2478b11f180e77faa71318e24"

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

# Step 1: Create chat with the right LLM but no fancy stuff yet — RAGFlow
# rejects most prompt fields on POST, so we set them via DB after.
body = json.dumps({
    "name": "bank-eval-clean",
    "dataset_ids": [NEW_KB_ID],
    "llm": {"model_name": "gpt-oss:120b-cloud@Ollama"},
}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:9380/api/v1/chats",
    data=body, method="POST",
    headers={"Authorization": f"Bearer {T}", "Content-Type": "application/json; charset=utf-8"},
)
import urllib.error
try:
    r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    print(f"create response: {json.dumps(r, ensure_ascii=False)[:300]}")
    if r.get("code") != 0:
        sys.exit(1)
    chat_id = r["data"]["id"]
    print(f"new chat id: {chat_id}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:300]}")
    sys.exit(1)

# Step 2: Force the prompt + reranker via DB (UI/API don't reliably persist them)
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

sql = (
    f"UPDATE dialog SET prompt_config = '{prompt_json_sql}', "
    f"rerank_id = 'qllama/bge-reranker-v2-m3:latest@Ollama', "
    f"tenant_rerank_id = 3 "
    f"WHERE id = '{chat_id}';"
)
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=sql.encode("utf-8"), capture_output=True,
)
print(f"db update rc: {result.returncode}")
if result.returncode != 0:
    print(f"stderr: {result.stderr.decode()[:300]}")

# Verify
verify = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow", "-N", "-e",
     f"SELECT id, name, llm_id, rerank_id FROM dialog WHERE id='{chat_id}';"],
    capture_output=True,
)
print(f"\n=== AFTER ===\n{verify.stdout.decode()}")
print(f"\nFINAL CHAT ID: {chat_id}")
