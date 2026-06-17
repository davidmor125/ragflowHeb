import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
OLLAMA='http://localhost:11434/api/chat'
JUDGE='gpt-oss:20b'
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
items={x['n']:x for x in json.load(open(f'{OUT}/eval_questions_parsed.json',encoding='utf-8'))}
data=json.load(open(f'{OUT}/eval_10pc.json',encoding='utf-8'))

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
    v.update({'n':r['n'],'label':r['label'],'ref_hit':r['ref_hit']})
    scored.append(v)
    print(f"Q{r['n']:02d} [{r['label']:14s}] verdict={v['verdict']:8s} ref_hit={r['ref_hit']} | {v.get('reason','')[:60]}")
save('eval_10pc_scored',scored)
from collections import Counter
c=Counter(s['verdict'] for s in scored)
hits=sum(1 for s in scored if s['ref_hit'])
print(f"\n=== 10-question result (parent_child + gemma4:31b-cloud, top_n=3) ===")
print(f"correct={c['correct']}/10 ({c['correct']*10}%)  partial={c['partial']}  wrong={c['wrong']}")
print(f"correct+partial={c['correct']+c['partial']}/10 ({(c['correct']+c['partial'])*10}%)")
print(f"reference hit: {hits}/10 ({hits*10}%)")
print("\nFAILURES (wrong or ref-miss):")
for s in scored:
    if s['verdict']=='wrong' or not s['ref_hit']:
        print(f"  Q{s['n']} [{s['label']}] verdict={s['verdict']} ref_hit={s['ref_hit']}: {s.get('reason','')[:90]}")
