"""Pick 20 questions that previously failed (kw=False or LLM=FAIL) for testing fixed canvas."""
import json

with open('/ragflow/eval_llm_judged.json', encoding='utf-8') as f:
    d = json.load(f)

# Failed = either kw_passed=False OR llm_verdict=FAIL
failed = [r for r in d['results'] if not r['kw_passed'] or r['llm_verdict'] == 'FAIL']
print(f"Failed pool: {len(failed)}")

# Pick 20 — diverse procedures, mix of types
seen_proc = set()
sample = []
for r in failed:
    if r['procedure'] in seen_proc and len(sample) < 15:
        continue
    sample.append(r)
    seen_proc.add(r['procedure'])
    if len(sample) >= 20:
        break

print(f"Picked: {len(sample)}")
for r in sample:
    print(f"  n={r['n']:>3} proc={r['procedure']:>5} kw={r['kw_passed']} llm={r['llm_verdict']}  Q: {r['question'][:60]}")

with open('/ragflow/_picked_20_failed.json', 'w', encoding='utf-8') as f:
    json.dump({'sample': sample}, f, ensure_ascii=False, indent=2)
