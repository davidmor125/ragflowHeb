"""Test 2 previously-failed questions through Agentic RAG v2."""
import sys, json, asyncio, time
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, UserCanvas
DB.connect(reuse_if_open=True)
from agent.canvas import Canvas

AGENT_ID = '05aea11c495211f180b9273574f6967d'  # banking_agentic_rag_v3

# Pick 2 questions that the v1 agent got wrong
TESTS = [
    {
        "q": "איך עושים העברת מט\"ח לאיחוד האמירויות",
        "expected_keywords": ["7528", "פרק ג'", "סעיף 10", "POP CODE", "AE", "פרטי העברה"],
        "gold": 'מתוך נוהל העברות מט"ח, מס\' 7528, פרק ג\' סעיף 10... יש לדווח בשדה "פרטי העברה" סיבת ההעברה: /BENEFRES/AE//xxx (xxx = POP CODE 3 תווים)',
    },
    {
        "q": "האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪",
        "expected_keywords": ["10,000", "25,000", "חשבון פרטי", "חשבון עסקי", "25%"],
        "gold": "כלולות אם: סכום מינימום חודשי 10,000 (פרטי) / 25,000 (עסקי), וחריגה של 25%+ מההצהרה",
    },
]

canvas = UserCanvas.get(UserCanvas.id == AGENT_ID)

async def go():
    for i, test in enumerate(TESTS, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {test['q']}")
        print(f"{'='*70}")
        print(f"Expected keywords: {test['expected_keywords']}")
        print(f"Gold (summary):    {test['gold'][:150]}")
        print()

        cnvs = Canvas(json.dumps(canvas.dsl), tenant_id=canvas.user_id, canvas_id=canvas.id)
        rewritten = ""
        retrieved_size = 0
        answer_parts = []
        final = None
        t0 = time.time()
        async for ev in cnvs.run(query=test['q']):
            if not isinstance(ev, dict): continue
            data = ev.get('data') or {}
            et = ev.get('event','')
            if et == 'node_finished' and isinstance(data, dict):
                cname = data.get('component_name','')
                outputs = data.get('outputs') or {}
                if cname == 'Query_Rewriter' and isinstance(outputs, dict):
                    rewritten = outputs.get('content', '')
                elif cname == 'Retrieval' and isinstance(outputs, dict):
                    retrieved_size = len(str(outputs.get('formalized_content','')))
                elif cname == 'Reply' and isinstance(outputs, dict):
                    final = outputs.get('content','')
            elif et == 'message':
                c = data.get('content') if isinstance(data, dict) else None
                if c: answer_parts.append(c)
            elif et == 'message_end':
                c = data.get('content') if isinstance(data, dict) else None
                if c: final = c
        elapsed = time.time() - t0
        answer = final if final else "".join(answer_parts)

        print(f"⏱  {elapsed:.0f}s")
        print(f"🔁 Rewritten query: {rewritten[:150]}")
        print(f"📚 Retrieved: {retrieved_size} chars of context")
        print()
        print(f"=== ANSWER ({len(answer)} chars) ===")
        print(answer)
        print()
        # Check keywords
        hits = [kw for kw in test['expected_keywords'] if kw.lower() in answer.lower()]
        print(f"Keywords matched: {len(hits)}/{len(test['expected_keywords'])}: {hits}")

asyncio.run(go())
