import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'   # SAME judge as baseline _eval_judge.py
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
baseline={x['n']:x for x in json.load(open(f'{OUT}/eval_scored.json',encoding='utf-8'))}

SYS=("אתה בודק איכות של מערכת שאלות-תשובה. נתונה שאלה, התשובה שהמערכת נתנה, "
     "וקטע המקור הנכון מהמסמך. דרג את התשובה: 'correct' אם היא עונה נכון ומבוססת "
     "על קטע המקור, 'partial' אם חלקית/חסרה, 'wrong' אם שגויה או 'לא נמצא מידע'. "
     "החזר JSON בלבד: {\"verdict\":\"correct|partial|wrong\",\"reason\":\"...\"}")

def judge(q,ans,src):
    user=f"שאלה: {q}\n\nתשובת המערכת: {ans}\n\nקטע המקור הנכון:\n{src[:1200]}"
    r=requests.post(OLLAMA,json={"model":JUDGE,"messages":[
        {"role":"system","content":SYS},{"role":"user","content":user}],
        "stream":False,"options":{"temperature":0}},timeout=300)
    txt=re.sub(r'^.*</think>','',r.json()['message']['content'],flags=re.DOTALL)
    m=re.search(r'\{.*\}',txt,re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return {"verdict":"wrong" if "לא נמצא" in ans else "partial","reason":"parse fail"}

variant=sys.argv[1]
data=json.load(open(f'{OUT}/eval_partials_variant{variant}.json',encoding='utf-8'))
print(f'=== Variant {variant} vs baseline (all were "partial" at baseline) ===\n')
scored=[]; improved=0; same=0; worse=0
for r in data:
    n=r['n']
    v=judge(r['question'],r['answer'],items[n]['expected_text'])
    base_v='partial'
    verdict=v['verdict']
    delta='= same'
    if verdict=='correct': delta='+ IMPROVED'; improved+=1
    elif verdict=='partial': same+=1
    else: delta='- WORSE'; worse+=1
    print(f"Q{n:02d}: baseline=partial -> variant{variant}={verdict:8s} {delta}")
    scored.append({"n":n,"verdict":verdict,"reason":v.get('reason','')[:150]})
    save(f'eval_partials_variant{variant}_scored_partial',scored)
save(f'eval_partials_variant{variant}_scored',scored)
print(f'\nVariant {variant}: improved->correct={improved}/12  still partial={same}  worse={worse}')
