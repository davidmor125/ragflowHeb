"""LLM-as-judge on a 20-question sample of the agent eval.
Sample is spread evenly across the 132 questions for representativeness."""
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
OUT = "/ragflow/eval_agent_sample20_judged.json"

JUDGE_LLM = "gpt-oss:120b-cloud@Ollama"
TENANT_ID = Dialog.get(Dialog.id == 'cf68bf1a46f011f196f633ac796a3d7a').tenant_id
mc = get_model_config_by_type_and_name(TENANT_ID, LLMType.CHAT, JUDGE_LLM)
bundle = LLMBundle(TENANT_ID, mc)

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
    prompt = (JUDGE_PROMPT
              .replace("{question}", q)
              .replace("{expected}", exp[:1500])
              .replace("{system}", sys_[:1500]))
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

    # Sample 20 questions evenly across the 132
    sample_indices = [int(i * len(results) / 20) for i in range(20)]
    sample = [results[i] for i in sample_indices]

    print(f"Judging {len(sample)}-question sample from 132 (every ~6.6 question)")
    print(f"Sample n's: {[r['n'] for r in sample]}")
    print()

    grades = {"PASS":0, "PARTIAL":0, "FAIL":0, "ERROR":0}
    keyword_pass_in_sample = sum(1 for r in sample if r['agent_passed'])
    print(f"Keyword grader in sample: {keyword_pass_in_sample}/20 PASS")
    print()

    sample_data = []
    for i, r in enumerate(sample, 1):
        ans = r.get('agent_answer') or ''
        gold = r['expected'] or ''
        if not gold or not ans:
            grade, reason = "FAIL", "empty"
        else:
            grade, reason = await judge_one(r['question'], gold, ans)

        kw_pass = r['agent_passed']
        agree = '✓' if (kw_pass == (grade == 'PASS')) else '✗'
        print(f"[{i:>2}/20] kw={('PASS' if kw_pass else 'FAIL')}  llm={grade:7}  {agree}  proc={r['procedure']:>5}  {r['question'][:60]}")
        print(f"        REASON: {reason[:120]}")

        grades[grade if grade in grades else "ERROR"] += 1
        sample_data.append({**r, 'llm_grade': grade, 'llm_reason': reason})
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'results': sample_data, 'progress': i}, f, ensure_ascii=False, indent=2)

    n = len(sample)
    print()
    print("=" * 60)
    print(f"SAMPLE 20 results")
    print(f"  Keyword PASS: {keyword_pass_in_sample}/20 ({100*keyword_pass_in_sample//n}%)")
    print(f"  LLM PASS:     {grades['PASS']}/{n}  ({100*grades['PASS']//n}%)")
    print(f"  LLM PARTIAL:  {grades['PARTIAL']}/{n}  ({100*grades['PARTIAL']//n}%)")
    print(f"  LLM FAIL:     {grades['FAIL']}/{n}  ({100*grades['FAIL']//n}%)")
    print()
    pp = grades['PASS'] + grades['PARTIAL']
    print(f"  LLM PASS+PARTIAL: {pp}/{n} ({100*pp//n}%)")

asyncio.run(main())
