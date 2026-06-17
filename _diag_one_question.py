"""Test ONE question directly with gpt-oss:20b — measure where time goes:
- retrieval time
- LLM call time
- Output length / quality
"""
import sys, asyncio, time, json
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
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
QUESTION = 'איך ניתן לבטל כרטיס אשראי בהתכתבות עם בנקאי?'

async def main():
    # 1) Retrieval
    print("Step 1: Retrieval", flush=True)
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)
    t0 = time.time()
    r = await s.retriever.retrieval(QUESTION, embd_mdl, [TENANT], [KB], 1, 15, 0.1, 0.3, top=1024, aggs=True, rerank_mdl=rerank_mdl)
    chunks = r.get('chunks', [])
    print(f"  retrieved {len(chunks)} chunks in {time.time()-t0:.1f}s", flush=True)
    formalized = "\n".join(kb_prompt(r, 200000, True))
    print(f"  formalized: {len(formalized)} chars", flush=True)

    # 2) LLM call with gpt-oss:20b
    print("\nStep 2: gpt-oss:20b LLM call", flush=True)
    chat_mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, 'gpt-oss:20b@Ollama')
    chat_mdl = LLMBundle(TENANT, chat_mc)
    sys_prompt = "אתה עוזר בנקאי. ענה בעברית בלבד על בסיס הנהלים שצורפו."
    user_prompt = f"שאלה: {QUESTION}\n\nנהלים:\n{formalized}\n\nתשובה (עברית בלבד):"
    print(f"  prompt total len: {len(sys_prompt) + len(user_prompt)}", flush=True)

    t1 = time.time()
    print(f"  calling LLM at {time.strftime('%H:%M:%S')}...", flush=True)
    try:
        ans = await asyncio.wait_for(
            chat_mdl.async_chat(sys_prompt, [{"role":"user","content":user_prompt}], {"temperature":0.1, "max_tokens": 800}),
            timeout=300
        )
        elapsed = time.time() - t1
        if isinstance(ans, tuple):
            ans = ans[0]
        print(f"  LLM done in {elapsed:.0f}s, output {len(ans)} chars", flush=True)
        print(f"\nANSWER:\n{ans}", flush=True)
    except asyncio.TimeoutError:
        elapsed = time.time() - t1
        print(f"  LLM TIMEOUT after {elapsed:.0f}s", flush=True)

asyncio.run(main())
