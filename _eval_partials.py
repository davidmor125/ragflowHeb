import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
OUT='_contract_out'
results={x['n']:x for x in json.load(open(f'{OUT}/eval_run50_results.json',encoding='utf-8'))}
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
scored={x['n']:x for x in json.load(open(f'{OUT}/eval_scored.json',encoding='utf-8'))}

partials=[n for n,s in scored.items() if s['verdict']=='partial']
print(f'{len(partials)} partial questions:',partials,'\n')
for n in sorted(partials):
    s=scored[n]; r=results[n]; it=items[n]
    # is the expected section content a table or gherkin?
    src=it['expected_text']
    kind='טבלה' if ('טבלה' in src or '/' in src[:200]) else ('Gherkin' if 'Given' in src else 'טקסט')
    print('='*95)
    print(f"Q{n} | פרק {r['expected_section']} | סוג מקור: {kind} | ref_hit={r['ref_hit']}")
    print(f"  שאלה: {it['question']}")
    print(f"  סיבת ה-judge: {s.get('reason','')}")
