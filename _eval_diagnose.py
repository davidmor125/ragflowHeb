import sys, json
sys.stdout.reconfigure(encoding='utf-8')
OUT='_contract_out'
results={x['n']:x for x in json.load(open(f'{OUT}/eval_run50_results.json',encoding='utf-8'))}
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
scored={x['n']:x for x in json.load(open(f'{OUT}/eval_scored.json',encoding='utf-8'))}

focus=[n for n,s in scored.items() if s['verdict'] in ('wrong','partial')]
print(f'Examining {len(focus)} non-perfect questions\n')
for n in sorted(focus):
    s=scored[n]; r=results[n]; it=items[n]
    print('='*90)
    print(f"Q{n} [{s['verdict']}] exp={r['expected_section']} ref_hit={r['ref_hit']} ref_sections={r['ref_sections']}")
    print(f"  Q: {it['question']}")
    print(f"  reason: {s.get('reason','')[:160]}")
    print(f"  ANSWER: {r['answer'][:260]}".replace(chr(10),' '))
    print(f"  EXPECTED (src): {it['expected_text'][:260]}".replace(chr(10),' '))
