import sys, json
sys.stdout.reconfigure(encoding='utf-8')
OUT='_contract_out'
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
A={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantA_scored.json',encoding='utf-8'))}
B={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantB_scored.json',encoding='utf-8'))}
Adata={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantA.json',encoding='utf-8'))}
Bdata={x['n']:x for x in json.load(open(f'{OUT}/eval_partials_variantB.json',encoding='utf-8'))}

print('Q   | A_verdict | B_verdict | combined-best')
best_correct=0
for n in sorted(A):
    av,bv=A[n]['verdict'],B[n]['verdict']
    best='correct' if 'correct' in (av,bv) else ('partial' if 'partial' in (av,bv) else 'wrong')
    if best=='correct': best_correct+=1
    print(f'Q{n:02d} | {av:8s} | {bv:8s} | {best}')
print(f'\nBest-of-either-variant correct: {best_correct}/12')

# show the still-partial / worse cases in detail
print('\n--- cases still NOT correct in BOTH variants ---')
for n in sorted(A):
    if A[n]['verdict']!='correct' and B[n]['verdict']!='correct':
        print(f"\nQ{n} ({items[n]['expected_section']}): {items[n]['question']}")
        print(f"  A reason: {A[n]['reason']}")
        print(f"  B reason: {B[n]['reason']}")
        print(f"  B answer head: {Bdata[n]['answer'][:160]}".replace(chr(10),' '))

# the WORSE case
print('\n--- Q24 WORSE in B ---')
print('B answer:',Bdata[24]['answer'][:300].replace(chr(10),' '))
print('B reason:',B[24]['reason'])
