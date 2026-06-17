import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'   # local judge
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

results=json.load(open(f'{OUT}/eval_run50_results.json',encoding='utf-8'))
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}

SYS=("אתה בודק איכות של מערכת שאלות-תשובה. נתונה שאלה, התשובה שהמערכת נתנה, "
     "וקטע המקור הנכון מהמסמך. דרג את התשובה: 'correct' אם היא עונה נכון ומבוססת "
     "על קטע המקור, 'partial' אם חלקית/חסרה, 'wrong' אם שגויה או 'לא נמצא מידע'. "
     "החזר JSON בלבד: {\"verdict\":\"correct|partial|wrong\",\"reason\":\"...\"}")

def judge(q,ans,src):
    user=f"שאלה: {q}\n\nתשובת המערכת: {ans}\n\nקטע המקור הנכון:\n{src[:1200]}"
    r=requests.post(OLLAMA,json={"model":JUDGE,"messages":[
        {"role":"system","content":SYS},{"role":"user","content":user}],
        "stream":False,"options":{"temperature":0}},timeout=300)
    txt=r.json()['message']['content']
    import re
    txt=re.sub(r'^.*</think>','',txt,flags=re.DOTALL)
    m=re.search(r'\{.*\}',txt,re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return {"verdict":"wrong" if "לא נמצא" in ans else "partial","reason":"judge parse fail"}

scored=[]
for r in results:
    src=items[r['n']]['expected_text']
    v=judge(r['question'],r['answer'],src)
    v['n']=r['n']; v['ref_hit']=r['ref_hit']; v['expected_section']=r['expected_section']
    v['no_info']=r['no_info']
    scored.append(v)
    print(f"Q{r['n']:02d} {v['verdict']:8s} hit={r['ref_hit']} | {v.get('reason','')[:70]}")
    save('eval_scored_partial',scored)

save('eval_scored',scored)
from collections import Counter
c=Counter(s['verdict'] for s in scored)
hits=sum(1 for s in scored if s['ref_hit'])
print(f"\nVERDICTS: {dict(c)}")
print(f"correct={c['correct']}/50 ({c['correct']*2}%)  partial={c['partial']}  wrong={c['wrong']}")
print(f"reference hit correct section: {hits}/50")
