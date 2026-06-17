"""Why did n=33, 80, 85 produce 'no procedures attached'?
Theory: retrieval IS returning chunks, but gemma4:26b for some reason
ignored them and assumed empty input. Test: directly run the same retrieval
and see what comes back.
"""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

CASES = [
    ('n=33 proc=11396', 'באיזה מקרים משתמשים בפעולת דיווח ערבות ללא טופל ממוכן?'),
    ('n=80 proc=18049', 'כיצד עלי לטפל שיש טעות בהדפסה'),
    ('n=85 proc=5088', 'על איזה טופס הלקוח צריך לחתום בהעברת מט"ח הונית;?'),
]

async def test(label, query):
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)

    r = await s.retriever.retrieval(
        query, embd_mdl, [TENANT], [KB], 1, 15, 0.1, 0.3, top=1024, aggs=True, rerank_mdl=rerank_mdl,
    )
    chunks = r.get('chunks', [])
    print(f"\n=== {label}")
    print(f"Q: {query}")
    print(f"Retrieved: {len(chunks)} chunks")
    for i, c in enumerate(chunks[:3], 1):
        cont = c.get('content_with_weight','') or c.get('content','')
        sim = c.get('similarity', 0)
        print(f"  #{i} sim={sim:.3f} doc={c.get('docnm_kwd','?')[:30]}  size={len(cont)}")
        print(f"     head: {cont[:200]}")

async def main():
    for label, q in CASES:
        await test(label, q)

asyncio.run(main())
