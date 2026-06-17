"""
Run 50 questions against the chap-1 RAG and grade each answer.
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

# 50 questions: each is (question, list_of_keywords_or_numbers_that_should_appear_in_answer)
QUESTIONS = [
    # ---- Table א'-1 (page 3) ----
    ("מה היה התוצר הנומינלי של ישראל בשנת 2018, במיליארדי ש\"ח?", ["1327"]),
    ("מה היה התוצר לנפש בישראל בשנת 2018, באלפי ש\"ח?", ["149"]),
    ("מה היה שיעור האבטלה הממוצע בישראל בשנת 2018?", ["4.0", "4%"]),
    ("מה היה שיעור האבטלה הממוצע בישראל בשנת 2013?", ["6.2"]),
    ("מה היה החוב הציבורי כאחוז מהתוצר ב-2018?", ["61"]),
    ("מה היה החוב הציבורי כאחוז מהתוצר ב-2013?", ["67"]),
    ("מה היה הגירעון הכולל של הממשלה הרחבה ב-2018, כאחוז מהתוצר?", ["3.8"]),
    ("מה היה גודל האוכלוסייה בישראל ב-2018, במיליונים?", ["8.9"]),
    ("מה היה יצוא הסחורות והשירותים ב-2018 במיליארדי דולרים?", ["103"]),
    ("מה היה יבוא הסחורות והשירותים ב-2018 במיליארדי דולרים?", ["102"]),
    ("מה היה שיעור הצמיחה של התוצר המקומי הגולמי ב-2018?", ["3.3"]),
    ("מה הייתה ריבית בנק ישראל הממוצעת ב-2018?", ["0.1"]),
    ("מה היה מספר המועסקים הישראלים ב-2018, באלפים?", ["3905", "3,905"]),
    ("מה היה שיעור עליית השכר הריאלי למשרת שכיר בשנת 2018?", ["2.7"]),
    ("מה הייתה האינפלציה ב-2018 (דצמבר לעומת דצמבר אשתקד)?", ["0.8"]),

    # ---- Image א'-1 (page 2) ----
    ("איך השתנה שיעור האבטלה בגילים 25-64 בישראל בין דצמבר 2009 לדצמבר 2018?", ["8", "ירידה", "אבטלה"]),
    ("מה תיאר איור א'-1?", ["אבטלה", "משרות", "פנויות", "תמורה"]),
    ("איזה צבע מציין באיור א'-1 את שיעור התמורה לעבודה במגזר העסקי?", ["כתום"]),
    ("איזה צבע מציין באיור א'-1 את שיעור המשרות הפנויות?", ["ירוק"]),

    # ---- Image א'-2 (page 5) ----
    ("מה תיאר איור א'-2?", ["אינפלציה", "מדד", "סחירים"]),
    ("איזה רכיב במדד האינפלציה הציג את התנודתיות הגדולה ביותר באיור א'-2?", ["סחירים", "אדום"]),
    ("מה הצבע המציין את מדד הדיור באיור א'-2?", ["כחול"]),

    # ---- Image א'-3 (page 6) ----
    ("מה תיאר איור א'-3?", ["OECD", "אינפלציה", "פעילות"]),

    # ---- Image א'-4 (page 7) ----
    ("מה הוצג באיור א'-4?", ["שער", "חליפין", "ריאלי", "אפקטיבי"]),
    ("ינואר באיזו שנה הוא בסיס לאיור א'-4?", ["2006"]),

    # ---- Image א'-5 (page 9) ----
    ("מה הוצג באיור א'-5?", ["תוצר", "לנפש", "מתקדמות"]),
    ("איזה צבע מציין את ישראל באיור א'-5?", ["כחול"]),

    # ---- Image א'-6 (page 13) ----
    ("מה הוצג באיור א'-6?", ["ריבית", "נומינלית", "ציפיות", "אינפלציה"]),
    ("מה היה הטווח של ציר ה-Y באיור א'-6?", ["1.5", "2.5"]),

    # ---- Image א'-7 (page 15) ----
    ("מה הוצג באיור א'-7?", ["מדינות", "ריבית", "אינדיקטורים"]),

    # ---- Image א'-8 (page 24) ----
    ("מה הוצג באיור א'-8?", ["השתתפות", "עבודה", "תרחיש"]),
    ("עד איזו שנה צופה איור א'-8?", ["2065"]),
    ("לפי איור א'-8, מה צפוי שיעור ההשתתפות ב-2065 בתרחיש שהחרדים והערבים מתכנסים במהירות?", ["87"]),

    # ---- Table א'-3 (page 22) ----
    ("מה התחזית של בנק ישראל לקצב הצמיחה השנתי של התוצר בתקופה 2015-2065?", ["2.4"]),
    ("מה היה קצב הצמיחה של התוצר בתקופה 2000-2015 לפי לוח א'-3?", ["3.3"]),
    ("מה הוא ההפרש בין הצמיחה בעבר לתחזית, לתוצר?", ["0.9", "-0.9"]),
    ("מה צפויה צמיחת ההון האנושי בתקופה 2015-2065?", ["1.8"]),
    ("מה היה קצב צמיחת ההון הפיזי לפי לוח א'-3 בעבר ב-1980-2015?", ["3.7"]),

    # ---- Table א'-4 (page 28) ----
    ("מה צפוי צמיחת התוצר השנתית בתחזית הבסיסית לפי לוח א'-4?", ["2.4"]),
    ("מה צפוי שיעור הסטייה של התוצר ב-2065 בתרחיש שיפור כל השינויים?", ["19.4"]),

    # ---- General text questions ----
    ("בכמה צמח המשק הישראלי ב-2018?", ["3.3"]),
    ("מה הייתה ריבית בנק ישראל ב-2018?", ["0.1"]),
    ("מה הוא קצב הצמיחה הפוטנציאלי שאליו מתייחס פרק א'?", ["3.3"]),
    ("איך התפתח התוצר לנפש ב-2018?", ["1.3"]),
    ("מתי הועלתה ריבית בנק ישראל לראשונה ב-2018?", ["נובמבר"]),

    # ---- Cross-table reasoning ----
    ("האם שיעור האבטלה ירד או עלה בין 2013 ל-2018?", ["ירד"]),
    ("האם החוב הציבורי כאחוז מהתוצר ירד או עלה בין 2013 ל-2018?", ["ירד"]),
    ("מה הייתה התשואה הנומינלית הממוצעת על אג\"ח ממשלתיות ל-10 שנים ב-2018?", ["2.2"]),
    ("מה הוא שיעור השינוי במדד ת\"א 3125 ב-2018?", ["-2.3"]),
    ("מה היה שער החליפין של השקל מול הדולר ב-2018 בממוצע שנתי?", ["3.6"]),
]

print(f"Total questions: {len(QUESTIONS)}")
print(f"Dialog: {dialog.name}")
print(f"LLM: {dialog.llm_id}")
print(f"KB ids: {dialog.kb_ids}")
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

def grade(answer, expected_keywords):
    if answer.startswith("[ERROR"):
        return False, "ERROR"
    if not answer or len(answer.strip()) < 5:
        return False, "EMPTY"
    # Strip citation markers like ##0$$
    clean = re.sub(r'##\d+\$\$', '', answer)
    clean = re.sub(r'\s+', ' ', clean)
    # Pass if ANY of the expected keywords appears in the answer (case-insensitive)
    for kw in expected_keywords:
        if kw.lower() in clean.lower():
            return True, kw
    return False, ", ".join(expected_keywords)

async def main():
    results = []
    pass_count = 0
    for i, (q, expected) in enumerate(QUESTIONS, 1):
        t0 = time.time()
        print(f"\n[{i}/{len(QUESTIONS)}] Q: {q}")
        ans = await ask(q)
        elapsed = time.time() - t0
        ok, info = grade(ans, expected)
        if ok:
            pass_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        # Truncate displayed answer
        ans_short = ans[:200].replace("\n", " ")
        print(f"  {status} ({elapsed:.1f}s) match={info}")
        print(f"  Answer: {ans_short}")
        results.append({
            "n": i, "question": q, "expected": expected, "answer": ans,
            "passed": ok, "match": info, "elapsed": round(elapsed, 1),
        })
        # Save incrementally so partial run is saved on crash
        with open("/ragflow/test_results.json", "w", encoding="utf-8") as f:
            json.dump({"pass": pass_count, "total": len(QUESTIONS), "results": results}, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print(f"FINAL: {pass_count}/{len(QUESTIONS)} passed ({100*pass_count//len(QUESTIONS)}%)")
    print("=" * 70)

asyncio.run(main())
