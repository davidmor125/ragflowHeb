import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
BASE='http://localhost:9380/api/v1'
H={'Authorization':'Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'}
DID='3db1df6c669d11f1b9e5df329cd4ee1f'
DOC='3e1a2c70669d11f1b9e5df329cd4ee1f'

chunks=[]; page=1
while True:
    ch=requests.get(f'{BASE}/datasets/{DID}/documents/{DOC}/chunks?page={page}&page_size=100',headers=H,timeout=60).json()
    cs=ch['data']['chunks']
    if not cs: break
    chunks.extend(cs); page+=1

# index chunks by their order; show which [S#] anchors each chunk contains
def anchors(c): return re.findall(r'\[S(\d+)[\]:]', c['content'])

print('=== Q1: Is a section title stored in metadata, or only inside content? ===')
print('   chunk fields:', sorted(chunks[0].keys()))
print('   -> NO dedicated title/heading field. Title lives ONLY inside `content` as [S#] text.\n')

# === Q2: the big section S21 (4480 tok). how many chunks does it span, do all carry the title? ===
print('=== Q2: section [S21] (the 4480-token one) — how is it split? ===')
s21=[(i,c) for i,c in enumerate(chunks) if '[S21]' in c['content'] or '[S21:' in c['content'] or re.search(r'\[S21[\]:]',c['content'])]
# broader: any chunk whose anchors include 21
s21=[(i,c) for i,c in enumerate(chunks) if '21' in anchors(c)]
print(f'   chunks containing [S21]: {len(s21)}')
for i,c in s21:
    tok=len(enc.encode(c['content']))
    a=anchors(c)
    has_title='[S21]' in c['content']
    head=c['content'][:70].replace('\n',' ')
    print(f'   chunk#{i} tok={tok} anchors_in_chunk={a} starts_with_S21_title={has_title}')
    print(f'      head: {head}')

# === how MANY sections per chunk (merging) ===
print('\n=== Q3: do chunks merge multiple sections, or split one? ===')
multi=[(i,anchors(c)) for i,c in enumerate(chunks) if len(set(anchors(c)))>1]
single_split=[]
# find sections that appear in >1 chunk (a section split across chunks)
from collections import defaultdict
sec2chunks=defaultdict(list)
for i,c in enumerate(chunks):
    for a in set(anchors(c)): sec2chunks[a].append(i)
split_secs={s:idxs for s,idxs in sec2chunks.items() if len(idxs)>1}
print(f'   chunks merging >1 section: {len(multi)} (e.g. {multi[:3]})')
print(f'   sections split across >1 chunk: {len(split_secs)}')
print(f'      examples: {dict(list(split_secs.items())[:5])}')

# For a split section, check: does the 2nd/3rd chunk still carry the [S#] title?
print('\n=== Q4: when a section IS split, does each piece keep its [S#] title? ===')
for s,idxs in list(split_secs.items())[:4]:
    print(f'   section S{s} -> chunks {idxs}:')
    for i in idxs:
        has = f'[S{s}]' in chunks[i]['content']
        head=chunks[i]['content'][:55].replace('\n',' ')
        print(f'      chunk#{i}: has_[S{s}]_title={has} | {head}')

# === Tables: find a big table section, see if it's one chunk or split, title kept ===
print('\n=== Q5: TABLE sections — kept whole? title kept? ===')
tbl=[(i,c) for i,c in enumerate(chunks) if '<table>' in c['content']]
print(f'   chunks containing <table>: {len(tbl)}')
for i,c in tbl[:4]:
    tok=len(enc.encode(c['content']))
    cap=re.search(r'\[S\d+[^\]]*\]', c['content'][:200])
    ntables=c['content'].count('<table>')
    print(f'   chunk#{i} tok={tok} tables_in_chunk={ntables} caption={cap.group(0) if cap else None}')
