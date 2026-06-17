"""Isolated test: do retrieval + format prompt ourselves, send to gemma4:26b directly.
Capture: how big is the formalized_content? What does gemma return on it?
"""
import sys, json, asyncio, time
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
from rag.prompts.generator import kb_prompt
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

CASES = [
    ('n=33', 'באיזה מקרים משתמשים בפעולת דיווח ערבות ללא טופל ממוכן?'),
    ('n=80', 'כיצד עלי לטפל שיש טעות בהדפסה'),
    ('n=85', 'על איזה טופס הלקוח צריך לחתום בהעברת מט"ח הונית;?'),
    ('n=91', 'מי צריך לשלם את העמלה בגין השמאות ?'),
]

SYS_PROMPT = (
    "אתה עוזר בנקאי שעונה רק על בסיס הנהלים שצורפו לשאלה.\n"
    "ענה בעברית בלבד, ישירות, מצטט סעיף ושם קובץ.\n"
    "אם המידע אינו בנהלים — כתוב בדיוק: 'המידע אינו קיים בנהלים שצורפו'.\n"
    "אסור לכתוב thinking, Step 1, We need, Wait — אסור לחלוטין.\n"
)

async def test(label, question):
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)

    t0 = time.time()
    r = await s.retriever.retrieval(
        question, embd_mdl, [TENANT], [KB], 1, 15, 0.1, 0.3, top=1024, aggs=True, rerank_mdl=rerank_mdl,
    )
    chunks = r.get('chunks', [])
    t_retr = time.time() - t0
    if not chunks:
        print(f"{label}: NO CHUNKS retrieved ({t_retr:.1f}s)")
        return

    formalized = "\n".join(kb_prompt(r, 200000, True))
    print(f"\n{'='*80}", flush=True)
    print(f"{label}: {question}", flush=True)
    print(f"  retrieval: {t_retr:.1f}s, {len(chunks)} chunks, formalized={len(formalized)} chars", flush=True)
    print(f"  formalized head (300c): {formalized[:300]}", flush=True)

    # Now send to gemma4:26b directly
    chat_mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, 'gemma4:26b@Ollama')
    chat_mdl = LLMBundle(TENANT, chat_mc)

    user_prompt = (
        f"שאלה: {question}\n\n"
        f"נהלים רלוונטיים:\n{formalized}\n\n"
        f"תשובה (עברית בלבד, ישירה):"
    )

    t1 = time.time()
    ans = await chat_mdl.async_chat(SYS_PROMPT, [{"role": "user", "content": user_prompt}],
                                     {"temperature": 0.1, "max_tokens": 800})
    t_llm = time.time() - t1
    print(f"  LLM: {t_llm:.1f}s, response={len(ans)}c", flush=True)
    print(f"  RESPONSE: {ans[-1500:]}", flush=True)

async def main():
    for label, q in CASES:
        await test(label, q)

asyncio.run(main())
