"""Pick the 12 questions that failed at the keyword grader (the original 'failed' set)."""
import json

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    d = json.load(f)

# Strict: only kw=False
kw_failed = [r for r in d['results'] if not r['kw_passed']]
print(f"kw=False count: {len(kw_failed)}")

# Take first 12
sample = kw_failed[:12]
print(f"\nSelected {len(sample)}:")
for r in sample:
    print(f"  n={r['n']:>3} proc={r['procedure']:>5}  Q: {r['question'][:60]}")

with open('/ragflow/_picked_12.json', 'w', encoding='utf-8') as f:
    json.dump({'sample': sample}, f, ensure_ascii=False, indent=2)
