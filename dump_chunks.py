"""Dump all chunks of a specific document to inspect chunk boundaries."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()

from api.db.db_models import DB, Document
DB.connect(reuse_if_open=True)

KB_ID = "055ff3d2478b11f180e77faa71318e24"

# Get all chunks for these docs by querying the doc store directly
retriever = s.retriever
docStore = s.docStoreConn

import asyncio

TARGETS = [
    ("78686.html", ["50,000", "500,000", "5,000 ₪"]),
    ("32904.html", ["בפעולות נוספות בכרטיס", "התכתבות עם בנקאי"]),
    ("31097.html", ["בנקאי בסניף", "פגישת פקיד מבצע", "חוצץ ראשי"]),
]


async def main():
    for fname, needles in TARGETS:
        print("=" * 80)
        print(f"Document: {fname}")
        # Find the doc
        docs = list(Document.select().where(Document.kb_id == KB_ID,
                                            Document.name.contains(fname.split('.')[0])))
        if not docs:
            print("  NOT FOUND")
            continue
        doc = docs[0]
        print(f"  doc_id={doc.id}  chunk_num={doc.chunk_num}")

        # Pull all chunks for this doc via search
        from rag.nlp.search import index_name
        idx = index_name(doc.tenant_id) if hasattr(doc, 'tenant_id') else None
        # Easier: use docStore directly
        from common import settings as cs
        # Use elasticsearch client through Dealer
        from rag.nlp import search as search_mod
        # search by doc_id via the dataStore
        from elasticsearch_dsl import Search

        # Get tenant via knowledgebase
        from api.db.db_models import Knowledgebase
        kb = Knowledgebase.get(Knowledgebase.id == KB_ID)
        tenant_id = kb.tenant_id

        try:
            res = docStore.search(
                ["content_with_weight", "docnm_kwd"],
                [],
                {"doc_id": doc.id},
                [],
                {},
                0, 1000,
                [search_mod.index_name(tenant_id)],
                [KB_ID],
            )
            chunks = docStore.get_fields(res, ["content_with_weight", "docnm_kwd"])
        except Exception as e:
            print(f"  search failed: {e}")
            continue

        items = list(chunks.items()) if isinstance(chunks, dict) else list(enumerate(chunks))
        print(f"  Retrieved {len(items)} chunk(s)")
        for i, (cid, payload) in enumerate(items, 1):
            content = (payload.get("content_with_weight") if isinstance(payload, dict) else payload) or ""
            content = content.replace("\n", " ")
            hits = [n for n in needles if n in content]
            marker = f"  HAS: {hits}" if hits else ""
            print(f"\n  --- chunk #{i} (id={cid[:12]}, {len(content)} chars){marker} ---")
            # Print first 250 + last 100 if long
            if len(content) > 400:
                print(f"  {content[:250]}")
                print(f"  ... [middle elided] ...")
                print(f"  {content[-150:]}")
            else:
                print(f"  {content}")
        print()


asyncio.run(main())
