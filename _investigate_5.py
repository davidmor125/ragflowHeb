import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
HJ={**H,'Content-Type':'application/json'}
DID='c8482642674011f1a56221ba47a3a9e1'

# the 5 real failures: (n, procedure, question, expected_key_phrase)
fails=[
 (4,'20071','במערכת תמנון+, בעת דיווח על פעולה בלתי רגילה, מתי יש לדווח על ההחלטה "תקין"','אינה חייבת בדיווח'),
 (7,'20064','האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪','10,000'),
 (9,'12917','מהן סמכויות האישור של פקיד מורשה','המידע אינו קיים'),
 (12,'78634','מהם הסניפים הרב מותגיים שהסניף המוביל שלה הוא אוצה"ח?','אוצה"ח חשמונאים'),
]

# map procedure -> doc id
docs=[];page=1
while True:
    rr=requests.get(f'{BASE}/datasets/{DID}/documents?page={page}&page_size=100',headers=H,timeout=60).json()
    b=rr['data']['docs']
    if not b: break
    docs.extend(b); page+=1
name2id={d['name']:d['id'] for d in docs}

for n,proc,q,phrase in fails:
    print('='*90)
    print(f'Q{n} [נוהל {proc}] phrase to find: "{phrase}"')
    docid=name2id.get(f'{proc}.html')
    if not docid:
        print(f'  *** doc {proc}.html NOT in dataset ***'); continue
    # is the expected phrase ANYWHERE in this procedure doc?
    chunks=[];page=1
    while True:
        ch=requests.get(f'{BASE}/datasets/{DID}/documents/{docid}/chunks?page={page}&page_size=200',headers=H,timeout=60).json()
        cs=ch['data']['chunks']
        if not cs: break
        chunks.extend(cs); page+=1
    allc='\n'.join(c['content'] for c in chunks)
    in_doc = phrase in allc
    print(f'  doc {proc}.html has {len(chunks)} chunks. Phrase in doc: {in_doc}')
    # which chunk contains it?
    if in_doc:
        for c in chunks:
            if phrase in c['content']:
                print(f'    found in chunk: ...{c["content"][max(0,c["content"].find(phrase)-40):c["content"].find(phrase)+80]}...'.replace(chr(10),' '))
                break
    # now: does retrieval (with rerank, restricted to this doc) surface it?
    r=requests.post(f'{BASE}/retrieval',headers=HJ,json={'question':q,'dataset_ids':[DID],
        'document_ids':[docid],'page_size':5,'similarity_threshold':0.0,
        'vector_similarity_weight':0.3,'keyword':True,'cross_languages':['Hebrew','English'],
        'rerank_id':'Qwen3-Reranker-4B@HuggingFace'},timeout=120).json()
    rch=r.get('data',{}).get('chunks',[])
    surfaced=any(phrase in c.get('content','') for c in rch)
    print(f'  retrieval RESTRICTED to {proc} surfaces phrase in top-5: {surfaced}')
    for c in rch[:3]:
        print(f'    sim={c.get("similarity",0):.3f} | {c["content"][:65].replace(chr(10)," ")}')
