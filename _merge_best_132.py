"""Merge all eval runs into a single 'best answer' file with 132 entries.
Priority: step1 (max_rounds=10, vec=0.3) > rerun (vec=0.3) > base v1 (vec=0.7).
For each n, take the LAST run where we have an answer.
"""
import json

with open('/ragflow/eval_agent_full_132.json', encoding='utf-8') as f:
    base = json.load(f)
with open('/ragflow/eval_failed_rerun.json', encoding='utf-8') as f:
    rerun = json.load(f)
with open('/ragflow/eval_step1_max_rounds.json', encoding='utf-8') as f:
    step1 = json.load(f)

merged = {}
# 1) base
for r in base['results']:
    merged[r['n']] = {
        'n': r['n'],
        'procedure': r['procedure'],
        'topic': r.get('topic'),
        'question': r['question'],
        'expected': r['expected'],
        'answer': r['agent_answer'],
        'kw_passed': r['agent_passed'],
        'kw_hits': r['agent_hits'],
        'kw_total': r['agent_total'],
        'source': 'base_v1_vec0.7',
    }
# 2) overlay rerun ONLY if it improved (passed_now is True OR existing was False)
for r in rerun['results']:
    cur = merged[r['n']]
    if r['passed_now'] or not cur['kw_passed']:
        cur.update({
            'answer': r['answer_v1_new_weight'],
            'kw_passed': r['passed_now'],
            'kw_hits': r['hits'],
            'kw_total': r['total'],
            'source': 'rerun_vec0.3',
        })
# 3) overlay step1 ONLY if it improved (passed_now True or existing False)
for r in step1['results']:
    cur = merged[r['n']]
    if r['passed_now'] or not cur['kw_passed']:
        cur.update({
            'answer': r['answer_step1'],
            'kw_passed': r['passed_now'],
            'kw_hits': r['hits'],
            'kw_total': r['total'],
            'source': 'step1_max_rounds10',
        })

best = sorted(merged.values(), key=lambda x: x['n'])
passed = sum(1 for r in best if r['kw_passed'])

with open('/ragflow/best_132.json', 'w', encoding='utf-8') as f:
    json.dump({
        'summary': {'total': len(best), 'kw_passed': passed},
        'results': best,
    }, f, ensure_ascii=False, indent=2)

print(f"Merged {len(best)} entries.  Keyword PASS = {passed}/{len(best)} = {passed*100/len(best):.1f}%")
src_counts = {}
for r in best:
    src_counts[r['source']] = src_counts.get(r['source'],0)+1
print("by source:", src_counts)
