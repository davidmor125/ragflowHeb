"""Deep diagnostic: for each failed question, retrieve a much wider top_n
(say 200) without rerank vs. with rerank, and see whether the chunk that
contains the gold-answer text appears at all, and at what rank.

This separates 3 possible root causes:
  A) chunking — the gold answer is split across chunk boundaries
  B) embedding/BM25 recall — the chunk exists but doesn't make top_k
  C) rerank — the chunk is in top_k but rerank pushes it down
"""
import sys, asyncio, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()

from api.db.db_models import DB, Dialog, Knowledgebase, Document
from api.db.services.dialog_service import get_models
from api.db.services.knowledgebase_service import KnowledgebaseService
DB.connect(reuse_if_open=True)

DIALOG_ID = "a7e5d00e478b11f180e77faa71318e24"
dialog = Dialog.get(Dialog.id == DIALOG_ID)
print(f"Dialog: {dialog.name}")
print(f"top_k={dialog.top_k}  top_n={dialog.top_n}  rerank={dialog.rerank_id}")
print()

# Build retriever like dialog_service.get_models does
kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl = get_models(dialog)
retriever = s.retriever
print(f"retriever={retriever}")

CASES = [
    {
        "n": 2, "proc": "78686",
        "question": "כמה כסף ניתן להפקיד בחשבון מקוון יחיד?",
        "needle_re": r"50,000|500,000|5,000\s*₪",
        "needle_desc": "deposit limits 50,000 / 500,000 / 5,000",
    },
    {
        "n": 3, "proc": "32904",
        "question": "איך ניתן לבטל כרטיס אשראי בהתכתבות עם בנקאי?",
        "needle_re": r"בפעולות נוספות בכרטיס|לינק.{0,20}ביטול כרטיס|התכתבות עם בנקאי",
        "needle_desc": "section 'התכתבות עם בנקאי' / 'בפעולות נוספות בכרטיס בדיגיטל'",
    },
    {
        "n": 7, "proc": "31097",
        "question": "איך לתאם פגישה ללקוח במערכת תנופה?",
        "needle_re": r"בנקאי בסניף.{0,5}מפנה|פגישת פקיד מבצע|חוצץ.{0,5}פגישות",
        "needle_desc": "section 2.3 'בנקאי בסניף מפנה' / 'פגישת פקיד מבצע'",
    },
]


def has_needle(chunk_text, pattern):
    if not chunk_text:
        return False
    return bool(re.search(pattern, chunk_text))


tenant_ids = list({kb.tenant_id for kb in kbs})


async def diag(case):
    print("=" * 80)
    print(f"Q#{case['n']}  proc={case['proc']}")
    print(f"Q: {case['question']}")
    print(f"Looking for: {case['needle_desc']}")
    print()

    # 1) Wide retrieval WITH rerank, top_n=200
    big_n = 200
    res = await retriever.retrieval(
        case["question"], embd_mdl, tenant_ids, dialog.kb_ids,
        1, big_n, 0.0, dialog.vector_similarity_weight,
        top=dialog.top_k, aggs=False,
        rerank_mdl=rerank_mdl,
    )
    chunks = res.get("chunks", [])
    print(f"  Wide retrieval (top_n={big_n}, with rerank): got {len(chunks)} chunks")

    target_chunks = [(i, c) for i, c in enumerate(chunks, 1)
                     if case["proc"] in (c.get("docnm_kwd") or "")]
    print(f"  Of those, {len(target_chunks)} are from procedure {case['proc']}")
    needle_in_target = [(i, c) for i, c in target_chunks
                        if has_needle(c.get("content_with_weight"), case["needle_re"])]
    print(f"  Of THOSE, {len(needle_in_target)} contain the gold-answer text")
    if needle_in_target:
        for r, c in needle_in_target[:3]:
            print(f"    rank #{r}  sim={c['similarity']:.3f}  vec={c.get('vector_similarity', 0):.3f}  term={c.get('term_similarity', 0):.3f}")
            print(f"      {(c['content_with_weight'] or '')[:200].replace(chr(10), ' ')}")
    else:
        print("    -> needle NOT found in any chunk from the target procedure")

    # 2) Same retrieval but WITHOUT rerank (raw embedding+BM25)
    res2 = await retriever.retrieval(
        case["question"], embd_mdl, tenant_ids, dialog.kb_ids,
        1, big_n, 0.0, dialog.vector_similarity_weight,
        top=dialog.top_k, aggs=False,
        rerank_mdl=None,
    )
    chunks2 = res2.get("chunks", [])
    target_chunks2 = [(i, c) for i, c in enumerate(chunks2, 1)
                      if case["proc"] in (c.get("docnm_kwd") or "")]
    needle_in_raw = [(i, c) for i, c in target_chunks2
                     if has_needle(c.get("content_with_weight"), case["needle_re"])]
    print(f"  Same retrieval WITHOUT rerank: needle in {len(needle_in_raw)} chunk(s)")
    if needle_in_raw:
        for r, c in needle_in_raw[:3]:
            print(f"    raw rank #{r}  sim={c['similarity']:.3f}  vec={c.get('vector_similarity', 0):.3f}  term={c.get('term_similarity', 0):.3f}")

    # 3) Look at the FULL doc — count chunks of this procedure
    docs = list(Document.select().where(Document.kb_id == dialog.kb_ids[0],
                                        Document.name.contains(case['proc'])))
    for d in docs:
        if case['proc'] in d.name:
            print(f"  Document {d.name}: has {d.chunk_num} chunks total in DB")
            break
    print()


async def main():
    for c in CASES:
        await diag(c)

asyncio.get_event_loop().run_until_complete(main())
