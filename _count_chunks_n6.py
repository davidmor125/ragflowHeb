"""Direct retrieval for n=6 — count chunks and analyze size distribution."""
import sys, asyncio
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
QUESTION = 'לקוח שלי מבקש להעביר כסף לרוסיה בגין רכישת דירה. האם עלי לדווח על פעולה בלתי רגילה'

async def main():
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)

    # vec_weight=0.3 like canvas now uses
    r = await s.retriever.retrieval(
        QUESTION, embd_mdl, [TENANT], [KB], 1, 15, 0.1, 0.3, top=1024, aggs=True, rerank_mdl=rerank_mdl,
    )
    chunks = r.get('chunks', [])
    print(f"top_n=15 returned {len(chunks)} chunks", flush=True)
    print()
    total_chars = 0
    for i, c in enumerate(chunks, 1):
        cont = c.get('content_with_weight','') or c.get('content','')
        total_chars += len(cont)
        sim = c.get('similarity', 0)
        nm = c.get('docnm_kwd', '?')[:40]
        print(f"  #{i:>2}  size={len(cont):>5}c  sim={sim:.3f}  doc={nm}", flush=True)
    print(f"\nSum of raw chunks: {total_chars}c")

    formalized = "\n".join(kb_prompt(r, 200000, True))
    print(f"After kb_prompt formatting: {len(formalized)}c")
    print(f"Overhead per chunk (avg): {(len(formalized)-total_chars)/len(chunks):.0f}c")

asyncio.run(main())
