import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests

# health
h=requests.get('http://localhost:8085/health',timeout=30).json()
print('health:',h)

# smoke test: Hebrew query + docs, one clearly relevant
q='מהם השלבים של תהליך התשלום?'
texts=[
    'תהליך התשלום כולל בחירת אמצעי תשלום, אישור הסכום, וקבלת חשבונית.',  # relevant
    'המערכת תומכת בעברית, אנגלית וערבית.',                               # irrelevant
    'גודל מקטע מרבי הוא 2048 אסימונים.',                                  # irrelevant
    'לאחר התשלום נשלחת הודעת SMS ללקוח עם פרטי ההזמנה.',                 # relevant
]
t0=time.time()
r=requests.post('http://localhost:8085/rerank',json={'query':q,'texts':texts,'raw_scores':False,'truncate':True},timeout=120)
dt=time.time()-t0
print(f'\nrerank {len(texts)} docs in {dt:.2f}s, status={r.status_code}')
res=r.json()
for o in sorted(res,key=lambda x:-x['score']):
    print(f'  score={o["score"]:.4f} | {texts[o["index"]][:50]}')

# verify ranking makes sense: relevant docs (0,3) should outrank irrelevant (1,2)
scores={o['index']:o['score'] for o in res}
ok = scores[0]>scores[1] and scores[0]>scores[2] and scores[3]>scores[2]
print(f'\nranking correct (relevant > irrelevant): {ok}')

# latency test with bigger batch (realistic: top_n candidates)
big=texts*5  # 20 docs
t0=time.time()
requests.post('http://localhost:8085/rerank',json={'query':q,'texts':big},timeout=180)
print(f'20-doc rerank latency: {time.time()-t0:.2f}s')
