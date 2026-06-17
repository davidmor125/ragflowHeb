import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'

# delete the failed markdown-vision doc to keep the dataset clean (evidence stays in s3_*.json)
fail_doc='79a0a338661f11f1ae84bd00f07a0952'
r=requests.delete(f'{BASE}/datasets/{DS}/documents',headers=HJ,json={'ids':[fail_doc]},timeout=30).json()
print('cleanup failed md doc:',r.get('code'))

# upload the PDF and parse (DeepDOC + tenant img2txt figure enrichment)
t_up0=time.time()
with open('_contract_testdoc_vision.pdf','rb') as fh:
    up=requests.post(f'{BASE}/datasets/{DS}/documents',headers=H,
        files={'file':('testdoc_vision.pdf',fh)},timeout=120).json()
t_up=time.time()-t_up0
docid=up['data'][0]['id']
save('s3_pdf_upload_response',up)
print(f'uploaded pdf doc {docid} in {t_up:.1f}s')

pr=requests.post(f'{BASE}/datasets/{DS}/chunks',headers=HJ,json={'document_ids':[docid]},timeout=30).json()
print('parse trigger code:',pr.get('code'))
t0=time.time(); last=None; d=None
while time.time()-t0<1800:
    docs=requests.get(f'{BASE}/datasets/{DS}/documents?id={docid}',headers=H,timeout=20).json()
    d=docs['data']['docs'][0]
    run,prog=str(d['run']),round(d.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} progress={prog}')
        last=(run,prog)
    if run in ('3','DONE') and d.get('progress',0)>=1: break
    if run=='4' or run=='FAIL':
        print('PARSE FAILED:',d.get('progress_msg','')[-400:]); save('s3_pdf_doc_final',d); sys.exit(1)
    time.sleep(5)
t_parse=time.time()-t0
save('s3_pdf_doc_final',d)
print(f'PDF parse done in {t_parse:.0f}s, chunks={d.get("chunk_count")}')
print('progress_msg tail:',d.get('progress_msg','')[-600:])

ch=requests.get(f'{BASE}/datasets/{DS}/documents/{docid}/chunks?page=1&page_size=200',headers=H,timeout=30).json()
save('s3_pdf_chunks',ch)
chunks=ch['data']['chunks']
allc=' '.join(c.get('content','') for c in chunks)
print('total chunks:',len(chunks))
for marker in ['PDFKEY77','12345-PDF','260','Q1','Q4','רבעון']:
    print(f'  marker {marker!r} present:',marker in allc)
img_chunks=[(c['id'],c.get('image_id','')) for c in chunks if c.get('image_id')]
print('chunks with image_id:',img_chunks)
print('S3_PDF_DOC_ID='+docid)
print('T_PARSE_PDF=%.1f'%t_parse)
