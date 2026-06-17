import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}; HJ={**H,'Content-Type':'application/json'}
OUT='_contract_out'
def save(n,o): json.dump(o,open(f'{OUT}/{n}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)

DS='2990101865ed11f19d1425719d627201'

# sanity: image reachable from inside the container
import subprocess
rc=subprocess.run(['docker','exec','docker-ragflow-cpu-1','sh','-c',
  'wget -q -O /dev/null http://host.docker.internal:8077/_contract_chart.png && echo OK || echo FAIL'],
  capture_output=True,text=True)
print('container can fetch chart over http:',rc.stdout.strip())
if 'OK' not in rc.stdout: sys.exit(1)

# build testdoc v2: same content, image referenced by URL instead of data-URI
src=open('_contract_testdoc.md',encoding='utf-8').read()
v2=re.sub(r'!\[תרשים מכירות\]\(data:image/png;base64,[^)]+\)',
          '![תרשים מכירות](http://host.docker.internal:8077/_contract_chart.png)',src)
assert 'host.docker.internal:8077' in v2, 'image ref substitution failed'
open('_contract_testdoc_v2.md','w',encoding='utf-8').write(v2)
print('testdoc v2 written, size:',len(v2))

# upload + parse
t0=time.time()
with open('_contract_testdoc_v2.md','rb') as fh:
    up=requests.post(f'{BASE}/datasets/{DS}/documents',headers=H,
        files={'file':('testdoc_vision.md',fh)},timeout=60).json()
docid=up['data'][0]['id']
save('s3_upload_response',up)
print('uploaded doc:',docid)
pr=requests.post(f'{BASE}/datasets/{DS}/chunks',headers=HJ,json={'document_ids':[docid]},timeout=30).json()
print('parse trigger code:',pr.get('code'))
t0=time.time(); last=None; d=None
while time.time()-t0<1200:
    docs=requests.get(f'{BASE}/datasets/{DS}/documents?id={docid}',headers=H,timeout=20).json()
    d=docs['data']['docs'][0]
    run,prog=str(d['run']),round(d.get('progress',0),2)
    if (run,prog)!=last:
        print(f'  [{int(time.time()-t0):4d}s] run={run} progress={prog}')
        last=(run,prog)
    if run in ('3','DONE') and d.get('progress',0)>=1: break
    if run=='4' or 'FAIL' in run.upper():
        print('PARSE FAILED:',d.get('progress_msg','')[-400:]); save('s3_doc_final',d); sys.exit(1)
    time.sleep(5)
t_parse=time.time()-t0
save('s3_doc_final',d)
print(f'parse done in {t_parse:.0f}s, chunks={d.get("chunk_count")}')
print('progress_msg tail:',d.get('progress_msg','')[-500:])

ch=requests.get(f'{BASE}/datasets/{DS}/documents/{docid}/chunks?page=1&page_size=200',headers=H,timeout=30).json()
save('s3_chunks',ch)
chunks=ch['data']['chunks']
allc=' '.join(c.get('content','') for c in chunks)
print('total chunks:',len(chunks))
for marker in ['260','Q1','Q2','Q3','Q4','רבעון','מכירות']:
    print(f'  marker {marker!r} present:',marker in allc)
img_chunks=[c['id'] for c in chunks if c.get('image_id')]
print('chunks with image_id:',img_chunks)
print('S3_DOC_ID='+docid)
