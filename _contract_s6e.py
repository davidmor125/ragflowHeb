import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

# ---- build ~200KB Hebrew markdown ----
paras=[]
topics=['רקע','ארכיטקטורה','עיבוד מסמכים','הטמעות','אחזור','דירוג','ניסוח','ציטוטים','העשרה','אבטחה']
i=0
while sum(len(p.encode('utf-8')) for p in paras)<200_000:
    i+=1
    t=topics[i%len(topics)]
    paras.append(f"## פרק {i}: {t}\n\nסעיף מספר {i} עוסק בנושא {t} של המערכת. "
        f"המערכת מעבדת מסמכים בצורה אוטומטית, מחלקת אותם למקטעים בגודל קבוע, מחשבת וקטורי הטמעה "
        f"רב-לשוניים, ומאחסנת אותם באינדקס. בעת שאילתה מאוחזרים המקטעים הדומים ביותר ומנוסחת תשובה "
        f"עם הפניות למקורות. מזהה ייחודי לפרק זה: SECTION-{i:04d}.\n")
big='# מסמך ביצועים גדול\n\n'+'\n'.join(paras)
open('_contract_big.md','w',encoding='utf-8').write(big)
size=os.path.getsize('_contract_big.md')
print(f'big md: {size/1024:.0f}KB, {len(paras)} sections')

# small txt
open('_contract_small.txt','w',encoding='utf-8').write(
    'קובץ טקסט פשוט לבדיקת זמני עיבוד. המערכת תומכת בקבצי txt רגילים.\n'*20)

# ---- fresh timing dataset: same chunking, NO LLM enrichment ----
ds_body={"name":"contract_timing_"+str(int(time.time())),"embedding_model":"bge-m3@Ollama",
  "chunk_method":"naive","parser_config":{"chunk_token_num":512,"layout_recognize":"DeepDOC",
  "auto_keywords":0,"auto_questions":0,"raptor":{"use_raptor":False}}}
ds=requests.post(f'{BASE}/datasets',headers=HJ,json=ds_body,timeout=30).json()
did=ds['data']['id']; print('timing dataset:',did)
save('s6_timing_dataset',ds)

def upload(path,name):
    with open(path,'rb') as fh:
        up=requests.post(f'{BASE}/datasets/{did}/documents',headers=H,files={'file':(name,fh)},timeout=120).json()
    return up['data'][0]['id']

def parse_and_wait(doc_ids,limit=2400):
    t0=time.time()
    requests.post(f'{BASE}/datasets/{did}/chunks',headers=HJ,json={'document_ids':doc_ids},timeout=30)
    while time.time()-t0<limit:
        docs=requests.get(f'{BASE}/datasets/{did}/documents?page_size=50',headers=H,timeout=20).json()
        dd={d['id']:d for d in docs['data']['docs']}
        states=[(str(dd[i]['run']),dd[i].get('progress',0)) for i in doc_ids]
        if all(r in ('3','DONE') and p>=1 for r,p in states): return time.time()-t0,dd
        if any(r in ('4','FAIL') for r,_ in states):
            for i in doc_ids:
                if str(dd[i]['run']) in ('4','FAIL'): print('FAILED:',dd[i]['name'],dd[i].get('progress_msg','')[-200:])
            return None,dd
        time.sleep(5)
    return None,dd

# measurement 1: big md alone
big_id=upload('_contract_big.md','big_200kb.md')
t_big,dd=parse_and_wait([big_id])
d=dd[big_id]
print(f'BIG MD (200KB): wall={t_big:.0f}s server_process_duration={d.get("process_duration")}s chunks={d.get("chunk_count")}')

# measurement 2: mixed batch (md + pdf-with-image + txt) parsed together
ids=[upload('_contract_testdoc_v3.md','testdoc.md'),
     upload('_contract_testdoc_vision.pdf','testdoc_vision.pdf'),
     upload('_contract_small.txt','small.txt')]
t_mix,dd=parse_and_wait(ids)
print(f'MIXED BATCH (3 files): wall={t_mix:.0f}s')
for i in ids:
    d=dd[i]; print(f'   {d["name"]}: process_duration={d.get("process_duration")}s chunks={d.get("chunk_count")}')

timing={"big_md_kb":round(size/1024),"big_md_wall_s":round(t_big or -1),
 "big_md_server_s":dd.get(big_id,{}).get('process_duration') if big_id in dd else None,
 "big_md_chunks":dd[big_id]['chunk_count'] if big_id in dd else None,
 "mixed_batch_wall_s":round(t_mix or -1),
 "mixed_files":[{ "name":dd[i]['name'],"server_s":dd[i].get('process_duration'),"chunks":dd[i]['chunk_count']} for i in ids],
 "note":"enrichment OFF in this dataset; enrichment cost measured separately in s2 (keywords ~1.0s/chunk, questions ~1.8s/chunk with gpt-oss:120b-cloud)",
 "pdf_with_image_and_enrichment_s":20.4}
save('s6_timing_summary',timing)
print('TIMING_DATASET='+did)
