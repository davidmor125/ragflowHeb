"""Pinpoint where in chunks the specific section text is."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()

from api.db.db_models import DB, Document, Knowledgebase
DB.connect(reuse_if_open=True)

KB_ID = "055ff3d2478b11f180e77faa71318e24"
kb = Knowledgebase.get(Knowledgebase.id == KB_ID)
docStore = s.docStoreConn

from rag.nlp import search as search_mod

CASES = [
    ("31097.html", [
        "בנקאי בסניף \" מפנה",
        "בנקאי בסניף \" מבצע",
        "פגישת פקיד מבצע",
        "2.3.",
    ]),
    ("32904.html", [
        "בפעולות נוספות בכרטיס",
        "ביטול כרטיס - בהתכתבות",
        "התכתבות עם בנקאי",
        "לשמר את הכרטיס",
    ]),
    ("78686.html", [
        "50,000",
        "500,000",
        "5,000",
    ]),
]

for fname, needles in CASES:
    print("=" * 80)
    print(f"Document: {fname}")
    docs = list(Document.select().where(Document.kb_id == KB_ID,
                                        Document.name.contains(fname.split('.')[0])))
    if not docs:
        print("  not found"); continue
    doc = docs[0]
    res = docStore.search(
        ["content_with_weight"], [], {"doc_id": doc.id}, [], {},
        0, 1000, [search_mod.index_name(kb.tenant_id)], [KB_ID],
    )
    chunks = docStore.get_fields(res, ["content_with_weight"])
    items = list(chunks.items()) if isinstance(chunks, dict) else list(enumerate(chunks))
    print(f"  {len(items)} chunks total")
    for i, (cid, payload) in enumerate(items, 1):
        content = (payload.get("content_with_weight") if isinstance(payload, dict) else payload) or ""
        for n in needles:
            if n in content:
                idx = content.find(n)
                ctx = content[max(0, idx-100): idx+200].replace("\n", " ")
                print(f"\n  needle '{n}' FOUND in chunk #{i} (size={len(content)}) at offset {idx}/{len(content)}")
                print(f"    ...{ctx}...")
    print()
