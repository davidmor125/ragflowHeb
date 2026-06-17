"""LLM judge v2 — strips English thinking-leak BEFORE grading.
Uses 5000-char window instead of 1500."""
import sys, json, asyncio, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()
from api.db.db_models import DB, Dialog
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
DB.connect(reuse_if_open=True)

IN  = "/ragflow/eval_agent_full_132.json"
OUT = "/ragflow/eval_agent_full_132_judged_v2.json"

JUDGE_LLM = "gpt-oss:120b-cloud@Ollama"
TENANT_ID = Dialog.get(Dialog.id == 'cf68bf1a46f011f196f633ac796a3d7a').tenant_id
mc = get_model_config_by_type_and_name(TENANT_ID, LLMType.CHAT, JUDGE_LLM)
bundle = LLMBundle(TENANT_ID, mc)

# Strip English thinking-leak: find first substantial Hebrew block and start there
HEB_RE = re.compile(r'[֐-׿]')

def strip_thinking(ans: str) -> str:
    """Remove English reasoning at the start. Find the first paragraph that's
    mostly Hebrew and use everything from there onwards."""
    if not ans:
        return ans
    # Split into paragraphs
    paragraphs = ans.split('\n')
    # Find the first paragraph that's >50% Hebrew chars
    for i, p in enumerate(paragraphs):
        non_space = [c for c in p if not c.isspace()]
        if len(non_space) < 20:
            continue
        heb = len([c for c in non_space if HEB_RE.match(c)])
        if heb / max(1, len(non_space)) > 0.5:
            # Hebrew-dominant — start from here
            return '\n'.join(paragraphs[i:]).strip()
    # No clearly-Hebrew paragraph found — return original
    return ans


JUDGE_PROMPT = """אתה שופט תשובות של מערכת RAG בנקאית.
ניתנת לך:
1. שאלה
2. תשובה צפויה (Gold)
3. תשובת המערכת

השווה לפי משמעות, לא ניסוח. דרג:
- PASS — התשובה מכסה את הליבה, עובדות עיקריות תואמות.
- PARTIAL — על הנושא הנכון אבל חסרות עובדות חשובות.
- FAIL — שגויה, מנוגדת, או "אין מידע" כשהמידע קיים.

חוקים:
- מספרים, סכומים, שמות מערכות חייבים להתאים בדיוק.
- אם Gold הוא הפניה לנוהל אחר והמערכת אמרה "אין מידע" — PARTIAL.

ענה JSON: {{"grade": "PASS|PARTIAL|FAIL", "reason": "explanation in Hebrew, max 1 sentence"}}

שאלה:
{question}

תשובה צפויה (Gold):
{expected}

תשובת המערכת:
{system}

JSON:"""

def parse_grade(text):
    if not text: return "ERROR", "empty"
    m = re.search(r'\{[^{}]*"grade"\s*:\s*"(PASS|PARTIAL|FAIL)".*?\}', text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj.get("grade","ERROR"), obj.get("reason","")
        except Exception:
            return m.group(1), ""
    for kw in ("PASS","PARTIAL","FAIL"):
        if kw in text.upper(): return kw, text[:120]
    return "ERROR", text[:120]


async def judge_one(q, exp, sys_):
    # Strip thinking-leak first
    sys_clean = strip_thinking(sys_)
    prompt = (JUDGE_PROMPT
              .replace("{question}", q)
              .replace("{expected}", exp[:5000])
              .replace("{system}", sys_clean[:5000]))
    try:
        resp = await bundle.async_chat(
            system="You are a precise judge. Output JSON only.",
            history=[{"role": "user", "content": prompt}],
            gen_conf={"temperature": 0.0},
        )
        if isinstance(resp, tuple): resp = resp[0]
        resp = re.sub(r'<think>.*?</think>', '', resp or '', flags=re.DOTALL)
        resp = re.sub(r'</?think>', '', resp)
        return parse_grade(resp)
    except Exception as e:
        return ("ERROR", str(e)[:120])


async def main():
    with open(IN, encoding='utf-8') as f:
        data = json.load(f)

    results = data['results']
    n = len(results)
    grades = {"PASS":0, "PARTIAL":0, "FAIL":0, "ERROR":0}
    print(f"v2 judge — strips English thinking, 5000-char window")
    print(f"Judging {n} agent answers")
    print()

    for i, r in enumerate(results, 1):
        ans = r.get('agent_answer') or ''
        gold = r['expected'] or ''
        if not gold or not ans:
            grade, reason = "FAIL", "empty"
        else:
            grade, reason = await judge_one(r['question'], gold, ans)

        r['llm_grade_v2'] = grade
        r['llm_reason_v2'] = reason
        grades[grade if grade in grades else "ERROR"] += 1

        if i % 5 == 0 or i == n:
            pp = grades['PASS'] + grades['PARTIAL']
            print(f"[{i:>3}/{n}] PASS={grades['PASS']} PARTIAL={grades['PARTIAL']} FAIL={grades['FAIL']} ERR={grades['ERROR']}  | PASS+PARTIAL={pp} ({100*pp//i}%)")

        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    pp = grades['PASS'] + grades['PARTIAL']
    print()
    print("=" * 60)
    print(f"FINAL ({n} questions)")
    print(f"  PASS:    {grades['PASS']}/{n}  ({100*grades['PASS']//n}%)")
    print(f"  PARTIAL: {grades['PARTIAL']}/{n}  ({100*grades['PARTIAL']//n}%)")
    print(f"  FAIL:    {grades['FAIL']}/{n}  ({100*grades['FAIL']//n}%)")
    print(f"  ERROR:   {grades['ERROR']}/{n}")
    print()
    print(f"  PASS+PARTIAL: {pp}/{n} ({100*pp//n}%)")

asyncio.run(main())
