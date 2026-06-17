import sys, json
sys.stdout.reconfigure(encoding='utf-8')
OUT='_contract_out'
C={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantC_scored.json',encoding='utf-8'))}
Cd={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantC.json',encoding='utf-8'))}
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
for n in [24,29,20,4]:
    print('='*80)
    print(f"Q{n} verdict={C[n]['verdict']}")
    print(f"  judge reason: {C[n]['reason']}")
    print(f"  GEMMA answer: {Cd[n]['answer'][:320]}".replace('\n',' '))
    print(f"  source snippet: {items[n]['expected_text'][:200]}".replace('\n',' '))
