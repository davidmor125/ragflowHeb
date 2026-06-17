"""
Run 60 NEW questions - different angles than the first 50.
Includes: cross-year comparisons, calculations, edge cases, paraphrased questions.
"""
import sys, json, time, asyncio, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()

from api.db.db_models import DB, Dialog
from api.db.services.dialog_service import async_chat

DB.connect(reuse_if_open=True)

DIALOG_ID = "300715ca42bd11f1a6bba9e87ac7a32c"
dialog = Dialog.get(Dialog.id == DIALOG_ID)
if not dialog.llm_id:
    dialog.llm_id = "gpt-oss:120b-cloud@Ollama"

QUESTIONS = [
    # ========= Year-by-year specifics from Table א'-1 =========
    ("מה היה התוצר הנומינלי בשנת 2014, במיליארדי ש\"ח?", ["1109"]),
    ("מה היה התוצר לנפש בשנת 2015, באלפי ש\"ח?", ["139"]),
    ("מה היה גודל האוכלוסייה בשנת 2015, במיליונים?", ["8.4"]),
    ("מה היה יצוא הסחורות והשירותים בשנת 2015 במיליארדי דולרים?", ["86.8", "86"]),
    ("מה היה יבוא הסחורות והשירותים בשנת 2015 במיליארדי דולרים?", ["78.2", "78"]),
    ("מה היה החשבון השוטף של מאזן התשלומים בשנת 2015?", ["16.1"]),
    ("מה היה הגירעון של הממשלה הרחבה בשנת 2015?", ["1.6"]),
    ("מה היה החוב הציבורי כאחוז מהתוצר בשנת 2015?", ["63.7", "63"]),
    ("מה היה מספר המועסקים בשנת 2015 באלפים?", ["3643", "3,643"]),
    ("מה הייתה האינפלציה בשנת 2015?", ["-1.0", "-1"]),

    # ========= 2017 questions =========
    ("מה היה התוצר הנומינלי בשנת 2017?", ["1271"]),
    ("מה הייתה ריבית בנק ישראל הממוצעת בשנת 2017?", ["0.1"]),
    ("מה היה שיעור האבטלה הממוצע בשנת 2017?", ["4.2"]),
    ("מה הייתה התשואה הנומינלית על אג\"ח ל-10 שנים בשנת 2017?", ["2.1"]),
    ("מה היה שיעור הצמיחה של התוצר בשנת 2017?", ["3.5"]),

    # ========= 2014 questions =========
    ("מה היה שיעור האבטלה בשנת 2014?", ["5.9"]),
    ("מה הייתה האינפלציה בשנת 2014?", ["-0.2"]),
    ("מה הייתה ריבית בנק ישראל הממוצעת בשנת 2014?", ["0.6"]),

    # ========= 2016 questions =========
    ("מה הייתה ריבית בנק ישראל הממוצעת בשנת 2016?", ["0.1"]),
    ("מה הייתה האינפלציה בשנת 2016?", ["-0.2"]),
    ("מה היה שיעור האבטלה בשנת 2016?", ["4.8"]),
    ("מה היה שיעור צמיחת הצריכה הפרטית בשנת 2016?", ["6.4"]),

    # ========= Cross-year comparisons / arithmetic =========
    ("בכמה גדלה האוכלוסייה בישראל בין 2013 ל-2018?", ["0.8", "0.7", "0.8 מיליון", "8.1", "8.9"]),
    ("בכמה אחוזים גדל התוצר הנומינלי בין 2013 ל-2018?", ["1057", "1327", "25", "26"]),
    ("מה הייתה הירידה בשיעור האבטלה בין 2013 ל-2018?", ["2.2", "6.2", "4.0"]),
    ("בכמה ירד החוב הציבורי כאחוז מהתוצר בין 2013 ל-2018?", ["6", "67", "61"]),

    # ========= Sechira/Sachar (Trade) =========
    ("מה היה שער החליפין של השקל מול הדולר בשנת 2015?", ["3.9"]),
    ("מה היה שער החליפין של השקל מול הדולר בשנת 2016?", ["3.8"]),
    ("מה היה שער החליפין הריאלי האפקטיבי בשנת 2018?", ["2.1"]),
    ("מה היה שיעור השינוי בסחר העולמי בשנת 2018?", ["4.0", "4"]),
    ("מה היה שיעור השינוי בסחר העולמי בשנת 2017?", ["5.3"]),

    # ========= Mortgage / Indices / Markets =========
    ("מה היה שיעור השינוי במדד ת\"א 3125 בשנת 2017?", ["6.4"]),
    ("מה היה שיעור השינוי במדד ת\"א 3125 בשנת 2013?", ["15.1"]),
    ("איך השתנה מדד ת\"א 3125 בשנת 2015?", ["2.0", "2"]),
    ("מה הייתה הריבית הריאלית לשנה בשנת 2018?", ["-0.8"]),
    ("מה הייתה הריבית הריאלית לשנה בשנת 2013?", ["-0.3"]),

    # ========= Detailed text understanding =========
    ("ב-2018, באיזה חודש הועלתה ריבית בנק ישראל?", ["נובמבר"]),
    ("בכמה הועלתה ריבית בנק ישראל לראשונה ב-2018?", ["0.25", "25"]),
    ("מה היה שיעור הצמיחה הפוטנציאלי של המשק לפי הפרק?", ["3.3"]),
    ("בכמה גדל סך השימושים במשק ב-2018 לעומת התוצר?", ["1.3", "3.3"]),

    # ========= Image א'-1 detail =========
    ("מה הטווח של ציר Y השמאלי באיור א'-1?", ["0", "8"]),
    ("מה הטווח של ציר Y הימני באיור א'-1?", ["58", "62"]),
    ("מה היה שיעור התמורה לעבודה במגזר העסקי בדצמבר 2015 לפי איור א'-1?", ["58.5", "58"]),

    # ========= Image א'-2 detail =========
    ("מהו טווח הערכים של ציר Y באיור א'-2?", ["-4", "4"]),
    ("איזה צבע מציין את מדד הסחירים באיור א'-2?", ["אדום"]),
    ("איזה צבע מציין את המדד הכללי באיור א'-2?", ["שחור"]),
    ("איזה צבע מציין את תחום יעד האינפלציה באיור א'-2?", ["אפור", "grey", "gray"]),

    # ========= Image א'-3 (OECD comparison) =========
    ("איזה צבע מציין את ישראל באיור א'-3?", ["כחול"]),
    ("מהן 4 התרשימים הקטנים שמופיעים באיור א'-3?", ["צריכה", "אינפלציה", "פער", "עלות"]),

    # ========= Image א'-4 (exchange rate) =========
    ("איזה קו באיור א'-4 מראה מגמת עלייה?", ["ירוק", "מחירים"]),
    ("מה היה הערך של שער החליפין הנומינלי האפקטיבי בסוף 2018 לפי איור א'-4?", ["60", "70", "65"]),

    # ========= Image א'-5 (per-capita GDP) =========
    ("איזה צבע מציין את המדינות המתקדמות באיור א'-5?", ["סגול", "purple"]),
    ("מה הייתה רמת היחס בין ישראל למדינות המתקדמות בשנת 2000 לפי איור א'-5?", ["0.55", "0.5"]),
    ("מה הייתה רמת היחס בין ישראל למדינות המתקדמות בשנת 2018 לפי איור א'-5?", ["0.9", "0.8"]),

    # ========= Image א'-6 (interest expectations) =========
    ("מה תיאר איור א'-6?", ["ריבית", "אינפלציה", "ציפיות"]),
    ("איזה צבע מציין את הציפיות משוק ההון לשנה באיור א'-6?", ["כחול"]),

    # ========= Image א'-8 (labor scenarios) =========
    ("בתרחיש שהחרדים והערבים אינם מתכנסים, מה צפוי שיעור ההשתתפות ב-2065?", ["78", "79"]),
    ("בתרחיש הבסיסי, מה צפוי שיעור ההשתתפות ב-2065?", ["84"]),
    ("איזה צבע מציין את התרחיש הבסיסי באיור א'-8?", ["כחול"]),

    # ========= Table א'-3 / א'-4 (forecasts) =========
    ("מה התחזית לתוצר לנפש בתקופה 2015-2065 לפי לוח א'-3?", ["0.7"]),
    ("מה התחזית לאוכלוסייה בתקופה 2015-2065?", ["1.7"]),
]

print(f"Total questions: {len(QUESTIONS)}")
print(f"LLM: {dialog.llm_id}")
print()

async def ask(question):
    messages = [{"role": "user", "content": question}]
    final_answer = ""
    try:
        async for chunk in async_chat(dialog, messages, stream=True):
            if isinstance(chunk, dict):
                ans = chunk.get("answer", "")
                if ans:
                    final_answer = ans
            elif isinstance(chunk, str):
                final_answer = chunk
    except Exception as e:
        return f"[ERROR: {e}]"
    return final_answer

def smart_grade(answer, expected):
    if not answer or len(answer.strip()) < 5:
        return False, "EMPTY"
    if answer.startswith("[ERROR"):
        return False, "ERROR"
    clean = re.sub(r'##\d+\$\$', '', answer)
    normalized = re.sub(r'(?<=\d)[,\s](?=\d)', '', clean)
    for kw in expected:
        kw_norm = re.sub(r'(?<=\d)[,\s](?=\d)', '', kw)
        if kw_norm.lower() in clean.lower() or kw_norm.lower() in normalized.lower():
            return True, kw
    return False, ", ".join(expected)

async def main():
    results = []
    pass_count = 0
    for i, (q, expected) in enumerate(QUESTIONS, 1):
        t0 = time.time()
        print(f"[{i}/{len(QUESTIONS)}] Q: {q}")
        ans = await ask(q)
        elapsed = time.time() - t0
        ok, info = smart_grade(ans, expected)
        if ok:
            pass_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        ans_short = ans[:150].replace("\n", " ")
        print(f"  {status} ({elapsed:.1f}s) match={info}")
        results.append({
            "n": i + 50, "question": q, "expected": expected, "answer": ans,
            "passed": ok, "match": info, "elapsed": round(elapsed, 1),
        })
        with open("/ragflow/test_results_60.json", "w", encoding="utf-8") as f:
            json.dump({"pass": pass_count, "total": len(QUESTIONS), "results": results}, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print(f"FINAL: {pass_count}/{len(QUESTIONS)} passed ({100*pass_count//len(QUESTIONS)}%)")
    print("=" * 70)

asyncio.run(main())
