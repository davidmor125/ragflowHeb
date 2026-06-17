import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'

# 4 retrieval-type failures (Q4,Q7 are type-A; Q9,Q12 type-B but test anyway)
cases=[
 (4,'20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"','אינה חייבת בדיווח'),
 (7,'20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪','10,000'),
 (12,'78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?','אוצה"ח חשמונאים'),
]

def retr(q, **kw):
    body={'question':q,'dataset_ids':[DID],'similarity_threshold':0.0,
          'keyword':True,'cross_languages':['Hebrew','English'],
          'rerank_id':'Qwen3-Reranker-4B@HuggingFace',**kw}
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json=body,timeout=300).json()
    return r.get('data',{}).get('chunks',[])

configs={
 'baseline top_n=8 vw=0.3': dict(page_size=8,vector_similarity_weight=0.3),
 'top_n=20 vw=0.3':         dict(page_size=20,vector_similarity_weight=0.3),
 'top_n=20 vw=0.5':         dict(page_size=20,vector_similarity_weight=0.5),
 'top_n=30 vw=0.7':         dict(page_size=30,vector_similarity_weight=0.7),
}

for n,proc,q,phrase in cases:
    print('='*80)
    print(f'Q{n} [{proc}] looking for "{phrase}"')
    for label,cfg in configs.items():
        ch=retr(q,**cfg)
        # rank of the chunk containing the phrase
        rank=-1
        for i,c in enumerate(ch):
            if phrase in c.get('content',''): rank=i+1; break
        right_proc=sum(1 for c in ch if proc in c.get('document_keyword',''))
        print(f'  {label:24s}: phrase_rank={rank if rank>0 else "NOT FOUND":>10} | chunks_from_{proc}={right_proc}/{len(ch)}')
