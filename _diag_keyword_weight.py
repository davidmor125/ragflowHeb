"""Test different keywords_similarity_weight values to find the best for Hebrew."""
import sys, asyncio, json
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
    {'proc': '7528',  'query': 'איך עושים העברת מט"ח לאיחוד האמירויות',
     'gold_phrases': ['פרק ג', 'איחוד האמירויות', 'POP CODE', 'BENEFRES']},
    {'proc': '20064', 'query': 'האם יש לעדכן את שאלון הכר את הלקוח בעת הוספת מורשה חתימה לחשבון',
     'gold_phrases': ['הכר את הלקוח', 'מורשה חתימה']},
    {'proc': '78686', 'query': 'כמה כסף ניתן להפקיד בחשבון מקוון יחיד',
     'gold_phrases': ['50,000', '500,000', '5,000']},
]

# In RAGFlow's retrieval API: vector_similarity_weight (NOT keywords_similarity_weight)
# 0.7 = 70% vector, 30% keyword (BM25)
# 0.3 = 30% vector, 70% keyword
# For Hebrew low-quality embeddings, lower vector weight = better
WEIGHTS = [0.7, 0.5, 0.3, 0.1]


async def test(case, vec_weight):
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)

    retriever = s.retriever
    results = await retriever.retrieval(
        case['query'], embd_mdl, [TENANT], [KB], 1, 15, 0.1, vec_weight,
        top=1024, aggs=True, rerank_mdl=rerank_mdl,
    )
    chunks = results.get('chunks', [])
    target_count = sum(1 for c in chunks if case['proc'] in c.get('docnm_kwd',''))
    gold_count = sum(1 for c in chunks
                     if any(g in (c.get('content_with_weight','') or c.get('content','') or '')
                            for g in case['gold_phrases']))
    return len(chunks), target_count, gold_count


async def main():
    for case in CASES:
        print(f"━━━ proc={case['proc']}: {case['query'][:60]} ━━━")
        for w in WEIGHTS:
            n, target, gold = await test(case, w)
            label = '★' if target > 0 else ' '
            print(f"  vec_weight={w}  retrieved={n:>2}  from_target={target:>2}  with_gold={gold:>2}  {label}")
        print()


asyncio.run(main())
