import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
from docx import Document
enc=tiktoken.get_encoding('cl100k_base')

# Parse the DOCX the way RAGFlow's naive docx path does: each Heading starts a
# section, body paragraphs/tables accumulate until next heading. We just want to
# find the biggest section to confirm what blows the embedder.
doc=Document('_client_spec.docx')
sections=[]
cur_title=None; cur_body=[]
def is_heading(p):
    return p.style and p.style.name and p.style.name.lower().startswith('heading')

# Walk body blocks in order (paragraphs + tables)
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
body=doc.element.body
def flush():
    if cur_title is not None or cur_body:
        txt=(cur_title or '')+'\n'+'\n'.join(cur_body)
        sections.append(txt)
for child in body.iterchildren():
    if child.tag==qn('w:p'):
        p=Paragraph(child,doc)
        if is_heading(p) and p.text.strip():
            flush()
            cur_title=p.text.strip(); cur_body=[]
        else:
            if p.text.strip(): cur_body.append(p.text.strip())
    elif child.tag==qn('w:tbl'):
        t=Table(child,doc)
        rows=[]
        for r in t.rows:
            rows.append(' | '.join(c.text.strip() for c in r.cells))
        cur_body.append('\n'.join(rows))
flush()

sizes=sorted([(len(enc.encode(s)),s[:70].replace('\n',' ')) for s in sections],reverse=True)
print(f'sections: {len(sections)}')
print('top 12 by cl100k tokens:')
for tk,prev in sizes[:12]:
    flag=' <-- EXCEEDS ~5500 Hebrew limit' if tk>5000 else ''
    print(f'  {tk:6d} tok | {prev}{flag}')
over=[tk for tk,_ in sizes if tk>5000]
print(f'\nsections over ~5000 cl100k tokens (Hebrew-risky): {len(over)}')
