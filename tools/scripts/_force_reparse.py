"""Force reparse of all 44 docs by directly inserting tasks into the queue.

Approach: instead of fighting RAGFlow's REST API for parse triggering,
we use the same internal mechanism RAGFlow itself uses - call queue_tasks()
from inside the container."""

import sys, json, subprocess
sys.stdout.reconfigure(encoding="utf-8")

# Build the in-container script that will trigger parsing
SCRIPT = """
import sys
sys.path.insert(0, '/ragflow')
from api.db.services.task_service import queue_tasks
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.file2document_service import File2DocumentService
from api.db import StatusEnum

KB_ID = '055ff3d2478b11f180e77faa71318e24'

# Get all docs in the KB
docs = DocumentService.query(kb_id=KB_ID)
print(f'found {len(docs)} docs')

queued = 0
for doc in docs:
    if doc.status != StatusEnum.VALID.value:
        continue
    doc_dict = doc.to_dict()
    # Get bucket and file name
    bucket, name = File2DocumentService.get_storage_address(doc_id=doc.id)
    try:
        queue_tasks(doc_dict, bucket, name, priority=0)
        # Reset status
        DocumentService.update_by_id(doc.id, {'progress': 0.0, 'progress_msg': '', 'run': '1'})
        queued += 1
        print(f'queued: {doc.name}')
    except Exception as e:
        print(f'FAIL {doc.name}: {e}')

print(f'queued {queued} tasks')
"""

# Copy and run inside container
with open(r"C:/develop/ragflow-main/tools/scripts/_force_reparse_inner.py", "w", encoding="utf-8") as f:
    f.write(SCRIPT)

subprocess.run(
    ["docker", "cp",
     r"C:/develop/ragflow-main/tools/scripts/_force_reparse_inner.py",
     "docker-ragflow-cpu-1:/tmp/reparse.py"],
    capture_output=True,
)

result = subprocess.run(
    ["docker", "exec", "docker-ragflow-cpu-1",
     "python3", "/tmp/reparse.py"],
    capture_output=True,
)
print("STDOUT:", result.stdout.decode("utf-8", errors="replace")[-2000:])
print("STDERR:", result.stderr.decode("utf-8", errors="replace")[-500:])
print("RC:", result.returncode)
