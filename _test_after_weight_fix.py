"""Test agent v1 (proven) with new vec_weight=0.3 on 5 questions."""
import sys, json, asyncio, time, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

# Use v1 (the better one — 84%)
AGENT_ID = '54e45b8048a011f18e412992204f7aa3'

TESTS = [
    {'q': 'איך עושים העברת מט"ח לאיחוד האמירויות',
     'expected_keywords': ['7528', "פרק ג'", 'פרק ג', 'POP', 'פרטי העברה']},
    {'q': 'האם יש לעדכן את שאלון הכר את הלקוח בעת הוספת מורשה חתימה לחשבון',
     'expected_keywords': ['כן', 'הכר את הלקוח', 'מורשה חתימה', 'עדכן']},
    {'q': 'כמה כסף ניתן להפקיד בחשבון מקוון יחיד?',
     'expected_keywords': ['50,000', '500,000', '5,000']},
    {'q': 'לקוח שלי מבקש להעביר כסף לרוסיה בגין רכישת דירה. האם עלי לדווח על פעולה בלתי רגילה',
     'expected_keywords': ['רוסיה', 'הלבנת הון', 'שחיתות', 'דיווח']},
    {'q': 'האם הבנק יכול להעלות ריבית ללקוח מיוזמתו?',
     'expected_keywords': ['יחיד', 'מסגרת', 'תיאום', 'הקטנת']},
]

canvas_obj = UserCanvas.get(UserCanvas.id == AGENT_ID)


async def ask(question):
    cnvs = Canvas(json.dumps(canvas_obj.dsl), tenant_id=canvas_obj.user_id, canvas_id=canvas_obj.id)
    answer_parts = []
    final = None
    try:
        async for ev in cnvs.run(query=question):
            if not isinstance(ev, dict): continue
            data = ev.get('data') or {}
            et = ev.get('event','')
            if et == 'message':
                c = data.get('content') if isinstance(data, dict) else None
                if c: answer_parts.append(c)
            elif et == 'message_end':
                c = data.get('content') if isinstance(data, dict) else None
                if c: final = c
            elif et == 'node_finished' and isinstance(data, dict):
                cname = data.get('component_name','')
                outputs = data.get('outputs') or {}
                if (cname.startswith('Reply') or data.get('component_type') == 'Message') and isinstance(outputs, dict):
                    if outputs.get('content'):
                        final = outputs['content']
    except Exception as e:
        return f"[ERROR: {e}]"
    return final if final else "".join(answer_parts)


def clean(answer):
    if not answer: return ""
    out = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    out = re.sub(r'</?think>', '', out)
    out = re.sub(r'##\d+\$\$', '', out)
    out = re.sub(r'\[ID:\d+\]', '', out)
    return re.sub(r'\s+', ' ', out).strip()


async def main():
    for i, test in enumerate(TESTS, 1):
        t0 = time.time()
        ans = await ask(test['q'])
        elapsed = time.time() - t0
        cleaned = clean(ans)
        hits = [kw for kw in test['expected_keywords'] if kw.lower() in cleaned.lower()]
        ok = len(hits) >= max(1, len(test['expected_keywords']) // 4)
        flag = '✅' if ok else '❌'
        print(f"#{i} {flag} {len(hits)}/{len(test['expected_keywords'])}kw {elapsed:.0f}s  {test['q'][:60]}")
        print(f"   matched: {hits}")
        print(f"   answer: {cleaned[:200]}")
        print()


asyncio.run(main())
