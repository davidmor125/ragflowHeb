"""Update bank-eval chat directly in MySQL since the RAGFlow UI Save is broken.

Sets:
  - prompt_config.system  → Hebrew banking-assistant prompt
  - prompt_config.empty_response → Hebrew "המידע אינו קיים במערכת"
  - prompt_config.prologue → Hebrew greeting
  - rerank_id  → qllama/bge-reranker-v2-m3:latest@Ollama
  - tenant_rerank_id → 3 (the tenant_llm id of that reranker)
"""

import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

CHAT_ID = "cf68bf1a46f011f196f633ac796a3d7a"
RERANK_ID_FULL = "qllama/bge-reranker-v2-m3:latest@Ollama"
TENANT_RERANK_ID = 3

NEW_SYSTEM = """את/ה עוזר/ת לבנקאי/ת בבנק. ענה/י על השאלה אך ורק על סמך הנהלים שצורפו למטה.

כללים:
1. ענה/י בעברית בלבד.
2. תן/י תשובה ישירה ומדויקת — בלי טבלאות, בלי סיכום של תוכן הקבצים, בלי הקדמות.
3. אם המידע מופיע במפורש בנהלים — צטט/י את הניסוח המדויק (במיוחד מספרים, סכומים, תקרות, גילאים, אחוזי ריבית).
4. אם המידע אינו מופיע בנהלים — ענה/י בדיוק: "המידע אינו קיים במערכת". אסור להמציא, אסור לנחש.
5. בסוף התשובה ציין/י את שם קובץ הנוהל שעליו הסתמכת.

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

# Serialize to JSON. MySQL JSON column accepts JSON literal.
prompt_json = json.dumps(new_prompt_config, ensure_ascii=False)

# Escape single quotes for SQL
prompt_json_sql = prompt_json.replace("\\", "\\\\").replace("'", "\\'")

sql = f"""UPDATE dialog
SET prompt_config = '{prompt_json_sql}',
    rerank_id = '{RERANK_ID_FULL}',
    tenant_rerank_id = {TENANT_RERANK_ID}
WHERE id = '{CHAT_ID}';"""

print("Running SQL update...")
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=sql.encode("utf-8"),
    capture_output=True,
)
print("stdout:", result.stdout.decode("utf-8", errors="replace"))
print("stderr:", result.stderr.decode("utf-8", errors="replace"))
print("returncode:", result.returncode)

# Verify
verify_sql = (
    f"SELECT id, llm_id, rerank_id, tenant_rerank_id, "
    f"SUBSTRING(prompt_config, 1, 300) AS p FROM dialog "
    f"WHERE id='{CHAT_ID}'\\G"
)
verify = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=verify_sql.encode("utf-8"),
    capture_output=True,
)
print()
print("=== AFTER ===")
print(verify.stdout.decode("utf-8", errors="replace"))
