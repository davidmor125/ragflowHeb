import json
d = json.load(open('eval_pipeline_v2_20.json', encoding='utf-8'))
print(f"Completed: {d['completed']}/{d['total']}")
print()
for r in d['results']:
    ans = r['pipeline_v2_answer']
    eng = sum(1 for c in ans if 'a'<=c.lower()<='z')
    heb = sum(1 for c in ans if 0x590<=ord(c)<=0x5ff)
    ratio = heb/(heb+eng+1)
    retr = r.get('retrieval_size', '?')
    print(f"n={r['n']:>3} retr={retr}c ans={len(ans)}c heb={ratio:.2f} {r['elapsed_s']}s")
