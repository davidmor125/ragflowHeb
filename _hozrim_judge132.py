import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
data=json.load(open(f'{OUT}/hozrim132_results.json',encoding='utf-8'))

SYS=("אתה בודק איכות של מערכת שאלות-תשובה על נהלים בנקאיים. נתונה שאלה, תשובת המערכת, "
     "והתשובה הנכונה (reference). דרג: 'correct' אם תשובת המערכת תואמת את התשובה הנכונה "
     "בעובדות המרכזיות, 'partial' אם חלקית/חסרה פרטים, 'wrong' אם שגויה או 'לא נמצא מידע'. "
     "החזר JSON בלבד: {\"verdict\":\"correct|partial|wrong\",\"reason\":\"...\"}")
def judge(q,ans,ref):
    u=f"שאלה: {q}\n\nתשובת המערכת: {ans}\n\nהתשובה הנכונה (reference):\n{ref[:1500]}"
    r=requests.post(OLLAMA,json={"model":JUDGE,"messages":[{"role":"system","content":SYS},
        {"role":"user","content":u}],"stream":False,"options":{"temperature":0}},timeout=300)
    t=re.sub(r'^.*</think>','',r.json()['message']['content'],flags=re.DOTALL)
    m=re.search(r'\{.*\}',t,re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return {"verdict":"wrong" if "לא נמצא" in ans else "partial","reason":"parse fail"}

scored=[]
for r in data:
    v=judge(r['question'],r['answer'],r['expected_answer'])
    v.update({'n':r['n'],'procedure':r['procedure'],'topic':r.get('topic'),'ref_hit':r['ref_hit']})
    scored.append(v)
    if r['n']%10==0: print(f"Q{r['n']:03d} {v['verdict']}")
    save('hozrim132_scored_partial',scored)
save('hozrim132_scored',scored)
from collections import Counter
c=Counter(s['verdict'] for s in scored)
hits=sum(1 for s in scored if s['ref_hit'])
n=len(scored)
print(f"\n=== HOZRIM 132 questions, full Qwen stack (no graphrag/raptor) ===")
print(f"correct={c['correct']}/{n} ({c['correct']*100//n}%)  partial={c['partial']}  wrong={c['wrong']}")
print(f"correct+partial={c['correct']+c['partial']}/{n} ({(c['correct']+c['partial'])*100//n}%)")
print(f"ref_hit={hits}/{n} ({hits*100//n}%)")
