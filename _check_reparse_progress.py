"""Check re-parse progress."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as s
s.init_settings()
from api.db.db_models import DB, Document
DB.connect(reuse_if_open=True)

KB = 'dc0091ca46e211f196f633ac796a3d7a'
docs = list(Document.select().where(Document.kb_id == KB))

by_run = {}
done_count = 0
running_count = 0
fail_count = 0
unstart_count = 0
total_progress = 0

for d in docs:
    run = str(d.run)
    by_run[run] = by_run.get(run, 0) + 1
    if d.progress:
        total_progress += d.progress
    if run == "3":
        done_count += 1
    elif run == "1":
        running_count += 1
    elif run == "4":
        fail_count += 1
    elif run == "0":
        unstart_count += 1

print(f"Total: {len(docs)}")
print(f"  DONE (run=3): {done_count}")
print(f"  RUNNING (run=1): {running_count}")
print(f"  FAILED (run=4): {fail_count}")
print(f"  UNSTART (run=0): {unstart_count}")
print(f"  Other: {by_run}")
print(f"  Avg progress: {total_progress/len(docs):.2f}")

# Show a few that are still running
running = [d for d in docs if str(d.run) == "1"][:5]
print(f"\nSample running:")
for d in running:
    print(f"  {d.name[:40]:40}  progress={d.progress:.2f}  msg={(d.progress_msg or '')[:60]}")

# Show a few failed
failed = [d for d in docs if str(d.run) == "4"][:5]
if failed:
    print(f"\nSample failed:")
    for d in failed:
        print(f"  {d.name[:40]:40}  msg={(d.progress_msg or '')[:100]}")
