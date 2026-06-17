import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
enc=tiktoken.get_encoding('cl100k_base')
OLLAMA='http://localhost:11434/api/embeddings'

doc=Document('_client_spec.docx')
def is_heading(p): return p.style and p.style.name and p.style.name.lower().startswith('heading')
sections=[]; cur_title=None; cur_body=[]
def flush():
    if cur_title is not None or cur_body:
        sections.append((cur_title,(cur_title or '')+'\n'+'\n'.join(cur_body)))
for child in doc.element.body.iterchildren():
    if child.tag==qn('w:p'):
        p=Paragraph(child,doc)
        if is_heading(p) and p.text.strip():
            flush(); cur_title=p.text.strip(); cur_body=[]
        elif p.text.strip(): cur_body.append(p.text.strip())
    elif child.tag==qn('w:tbl'):
        t=Table(child,doc)
        cur_body.append('\n'.join(' | '.join(c.text.strip() for c in r.cells) for r in t.rows))
flush()

def embed_ok(txt):
    r=requests.post(OLLAMA,json={'model':'bge-m3','prompt':txt},timeout=180)
    return r.status_code, ('embedding' in r.json() if r.status_code==200 else r.text[:80])

# test each section individually
print('Testing each section against live bge-m3:')
fails=[]
for title,txt in sections:
    tk=len(enc.encode(txt))
    if tk<1500: continue  # only test the big ones
    code,res=embed_ok(txt)
    mark='OK' if res is True else f'FAIL {res}'
    if res is not True: fails.append((title,tk))
    print(f'  {tk:5d}tok {mark}  | {(title or "")[:45]}')
print(f'\nsections that FAIL embedding individually: {len(fails)}')
for t,tk in fails: print(f'   {tk}tok {t}')
