import sys, json
sys.stdout.reconfigure(encoding='utf-8')
OUT='_contract_out'
E={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantE_scored.json',encoding='utf-8'))}
Ed={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantE.json',encoding='utf-8'))}
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
for n in [20,24]:
    print('='*85)
    print(f"Q{n} verdict={E[n]['verdict']}  (judge says WRONG)")
    print(f"  judge reason: {E[n]['reason']}")
    print(f"  GEMMA-31b answer: {Ed[n]['answer'][:400]}".replace('\n',' '))
    print(f"  TRUE source: {items[n]['expected_text'][:280]}".replace('\n',' '))
