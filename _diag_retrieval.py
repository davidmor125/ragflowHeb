"""Diagnose why Retrieval doesn't return the chunks with gold answers."""
import sys, asyncio, json
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
from rag.nlp import search as search_mod
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

CASES = [
    {
        'proc': '7528',
        'query': 'איך עושים העברת מט"ח לאיחוד האמירויות',
        'gold_phrases': ['פרק ג', 'איחוד האמירויות', 'POP CODE', 'BENEFRES'],
    },
    {
        'proc': '20064',
        'query': 'האם יש לעדכן את שאלון הכר את הלקוח בעת הוספת מורשה חתימה לחשבון',
        'gold_phrases': ['הכר את הלקוח', 'מורשה חתימה'],
    },
    {
        'proc': '78686',
        'query': 'כמה כסף ניתן להפקיד בחשבון מקוון יחיד',
        'gold_phrases': ['50,000', '500,000', '5,000'],
    },
]


async def diag(case):
    print('='*70)
    print(f"Case: proc={case['proc']}  Q: {case['query']}")
    print('='*70)

    # Find doc
    docs = list(Document.select().where(Document.kb_id == KB))
    target = next((d for d in docs if case['proc'] in (d.name or '')), None)
    if not target:
        print('  doc not found')
        return

    # Get all chunks from this doc, find the one(s) with gold
    res = s.docStoreConn.search(['content_with_weight'], [], {'kb_id': KB, 'doc_id': target.id}, [], {}, 0, 200,
                                  [search_mod.index_name(TENANT)], [KB])
    items = list(s.docStoreConn.get_fields(res, ['content_with_weight']).values())
    print(f"  {target.name} has {len(items)} chunks")
    chunks_with_gold = []
    for i, p in enumerate(items):
        text = (p.get('content_with_weight','') if isinstance(p, dict) else '')
        matches = [g for g in case['gold_phrases'] if g in text]
        if matches:
            chunks_with_gold.append((i, len(text), matches))
    print(f"  {len(chunks_with_gold)} chunks contain gold phrases:")
    for i, sz, matches in chunks_with_gold[:5]:
        print(f"    chunk #{i}  size={sz}  matches: {matches}")
    print()

    # Now do actual retrieval
    embd_mc = get_model_config_by_type_and_name(TENANT, LLMType.EMBEDDING, 'bge-m3@Ollama')
    embd_mdl = LLMBundle(TENANT, embd_mc)
    rerank_mc = get_model_config_by_type_and_name(TENANT, LLMType.RERANK, 'BAAI/bge-reranker-v2-m3@HuggingFace')
    rerank_mdl = LLMBundle(TENANT, rerank_mc)

    retriever = s.retriever
    results = await retriever.retrieval(
        case['query'], embd_mdl, [TENANT], [KB], 1, 15, 0.1, 0.7, top=1024, aggs=True,
        rerank_mdl=rerank_mdl,
    )
    chunks = results.get('chunks', [])
    print(f"  Retrieved top-15 chunks:")
    target_in_top = 0
    gold_in_top = 0
    for i, c in enumerate(chunks, 1):
        nm = c.get('docnm_kwd', '')
        cont = c.get('content_with_weight','') or c.get('content','')
        sim = c.get('similarity', 0)
        is_target = case['proc'] in nm
        has_gold = any(g in cont for g in case['gold_phrases'])
        flag = ''
        if is_target:
            target_in_top += 1
            flag += ' ★FROM_TARGET'
        if has_gold:
            gold_in_top += 1
            flag += ' ✓HAS_GOLD'
        print(f"    #{i:>2}  sim={sim:.3f}  {nm[:40]:40}{flag}")
    print()
    print(f"  Chunks from {case['proc']} in top-15:  {target_in_top}")
    print(f"  Chunks with gold text in top-15:    {gold_in_top}")
    if gold_in_top == 0:
        print(f"  ⚠ GOLD CHUNK NOT IN TOP-15 — that's why answer fails!")
    print()


async def main():
    for c in CASES:
        await diag(c)

asyncio.run(main())
