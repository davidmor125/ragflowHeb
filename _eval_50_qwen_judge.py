import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
data=json.load(open(f'{OUT}/eval_50qwen.json',encoding='utf-8'))

SYS=("אתה בודק איכות. נתונה שאלה, תשובת המערכת, וקטע המקור הנכון. דרג: "
     "'correct' אם עונה נכון ומבוסס על המקור, 'partial' אם חלקי, 'wrong' אם שגוי או 'לא נמצא מידע'. "
     "החזר JSON: {\"verdict\":\"correct|partial|wrong\",\"reason\":\"...\"}")
def judge(q,ans,src):
    u=f"שאלה: {q}\n\nתשובת המערכת: {ans}\n\nקטע המקור:\n{src[:1200]}"
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
    v=judge(r['question'],r['answer'],items[r['n']]['expected_text'])
    v.update({'n':r['n'],'ref_hit':r['ref_hit']})
    scored.append(v)
    print(f"Q{r['n']:02d} {v['verdict']:8s} hit={r['ref_hit']}")
    save('eval_50qwen_scored_partial',scored)
save('eval_50qwen_scored',scored)
from collections import Counter
c=Counter(s['verdict'] for s in scored)
hits=sum(1 for s in scored if s['ref_hit'])
print(f"\n=== FULL QWEN STACK, 50 questions ===")
print(f"correct={c['correct']}/50 ({c['correct']*2}%)  partial={c['partial']}  wrong={c['wrong']}")
print(f"correct+partial={c['correct']+c['partial']}/50 ({(c['correct']+c['partial'])*2}%)")
print(f"ref_hit={hits}/50 ({hits*2}%)")

# compare to bge-m3 baseline (eval_scored.json)
try:
    bge={x['n']:x['verdict'] for x in json.load(open(f'{OUT}/eval_scored.json',encoding='utf-8'))}
    bc=Counter(bge.values())
    print(f"\n=== vs bge-m3 baseline ===")
    print(f"bge-m3:     correct={bc['correct']}/50  partial={bc['partial']}  wrong={bc['wrong']}")
    print(f"Qwen stack: correct={c['correct']}/50  partial={c['partial']}  wrong={c['wrong']}")
    ups=[s['n'] for s in scored if bge.get(s['n'])!='correct' and s['verdict']=='correct']
    downs=[s['n'] for s in scored if bge.get(s['n'])=='correct' and s['verdict']!='correct']
    print(f"improved to correct: {ups}")
    print(f"regressed from correct: {downs}")
except Exception as e: print('compare skip:',e)
