import sys
sys.stdout.reconfigure(encoding='utf-8')
from api.db.db_models import DB, Document, Knowledgebase
DB.connect(reuse_if_open=True)
print('=== Knowledge Bases ===')
for kb in Knowledgebase.select():
    print(f'  kb_id={kb.id[:12]}... name={kb.name!r} tenant={kb.tenant_id[:8]}...')
print()
print('=== Documents containing "chap" ===')
for d in Document.select().where(Document.name.contains('chap')):
    print(f'  doc_id={d.id} name={d.name!r} kb={d.kb_id[:12]}... status={d.status} progress={d.progress} type={d.type}')
print()
print('=== All documents ===')
for d in Document.select().limit(20):
    print(f'  doc_id={d.id} name={d.name!r} kb={d.kb_id[:12]}... progress={d.progress}')
