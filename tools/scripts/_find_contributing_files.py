"""For each of the 10 questions, run retrieval against the big hozrim KB
and list every file that contributed a chunk. We'll merge the union and
that's the set the user needs to add to test_five_files."""

import sys, json, urllib.request
from pathlib import Path
import openpyxl

sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB_BIG = "dc0091ca46e211f196f633ac796a3d7a"

# Read first 10 data rows from Excel
wb = openpyxl.load_workbook(
    r"C:/develop/html_output/_eval_report/newtest/test_report_24_05.xlsx",
    read_only=True, data_only=True,
)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

questions = []
for r in rows[5:]:
    nohel, q = r[1], r[4]
    if nohel and q:
        questions.append((str(nohel).strip(), str(q).strip()))
        if len(questions) >= 10:
            break

# For each question, retrieve top chunks. Take any file that contributes
# >= 1 chunk into top-K. We take TOP_K=10 per question to keep relevance high.
TOP_K = 10
TOP_FILES_PER_Q = 6   # surface only the top-6 most relevant docs per Q

all_files: dict[str, list[tuple[int, str, float]]] = {}

for q_idx, (nohel, q) in enumerate(questions, 1):
    body = json.dumps({
        "dataset_ids": [KB_BIG],
        "question": q,
        "top_k": TOP_K,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:9380/api/v1/retrieval",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {T}", "Content-Type": "application/json; charset=utf-8"},
    )
    r = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
    chunks = r.get("data", {}).get("chunks", [])

    docs: dict[str, list[float]] = {}
    for c in chunks:
        if not isinstance(c, dict):
            continue
        name = c.get("document_keyword", "?")
        sim = c.get("similarity", 0)
        docs.setdefault(name, []).append(sim)

    sorted_docs = sorted(docs.items(), key=lambda x: -max(x[1]))[:TOP_FILES_PER_Q]
    print(f"\nQ{q_idx} (נוהל={nohel}): {q[:60]}")
    for name, sims in sorted_docs:
        marker = " <- expected" if f"{nohel}.html" in name else ""
        print(f"  best={max(sims):.3f}  {len(sims)}x  {name[:60]}{marker}")
        # Strip "טסט/" prefix if present, keep just the basename
        bn = name.replace("טסט/", "")
        all_files.setdefault(bn, []).append((q_idx, name, max(sims)))

# Final list of files to upload
print("\n" + "=" * 70)
print("UNIQUE FILES TO UPLOAD TO test_five_files:")
print("=" * 70)
sorted_files = sorted(all_files.items(), key=lambda x: -len(x[1]))
for fname, hits in sorted_files:
    qs = sorted(set(h[0] for h in hits))
    print(f"  {fname}    (relevant for Q: {qs})")

print(f"\nTOTAL: {len(sorted_files)} files")
print()
print("File list (just names):")
for fname, _ in sorted_files:
    print(f"  {fname}")
