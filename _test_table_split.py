import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,'.')
import re, copy
from common.token_utils import num_tokens_from_string

# replicate the function standalone to test logic (no heavy imports)
def tokenize(d, txt, eng):
    d["content_with_weight"]=txt
def split_table_into_children(d, html, eng, max_child_tokens=256):
    caption_m=re.search(r"<caption>.*?</caption>",html,flags=re.DOTALL)
    caption=caption_m.group(0) if caption_m else ""
    rows=re.findall(r"<tr>.*?</tr>",html,flags=re.DOTALL)
    if not rows: return []
    header=rows[0] if rows else ""
    body=rows[1:] if len(rows)>1 else rows
    children=[]; batch=[]; batch_tokens=num_tokens_from_string(caption+header)
    for row in body:
        rt=num_tokens_from_string(row)
        if batch and batch_tokens+rt>max_child_tokens:
            ch="<table>"+caption+header+"".join(batch)+"</table>"
            dd=copy.deepcopy(d); tokenize(dd,ch,eng); dd["doc_type_kwd"]="table"; children.append(dd)
            batch=[]; batch_tokens=num_tokens_from_string(caption+header)
        batch.append(row); batch_tokens+=rt
    if batch:
        ch="<table>"+caption+header+"".join(batch)+"</table>"
        dd=copy.deepcopy(d); tokenize(dd,ch,eng); dd["doc_type_kwd"]="table"; children.append(dd)
    return children

# build a realistic big Hebrew table like S44
caption='<caption>Table Location: client_spec > [S44] אפיון בסיס נתונים — מילון נתונים (טבלאות)</caption>'
header='<tr><td>ישות</td><td>שדה</td><td>סוג</td><td>מפתח</td><td>תיאור</td></tr>'
rows=''.join(f'<tr><td>לקוח</td><td>שדה{i}</td><td>string</td><td>לא</td><td>תיאור מפורט של שדה מספר {i} בטבלת הנתונים</td></tr>' for i in range(40))
html='<table>'+caption+header+rows+'</table>'
print('original table tokens:',num_tokens_from_string(html))

children=split_table_into_children({},html,False,max_child_tokens=256)
print('children produced:',len(children))
for i,c in enumerate(children):
    t=num_tokens_from_string(c['content_with_weight'])
    has_cap='[S44]' in c['content_with_weight']
    has_hdr='<td>ישות</td>' in c['content_with_weight']
    print(f'  child {i}: tok={t} has_caption[S44]={has_cap} has_header={has_hdr}')
# assertions
assert all(num_tokens_from_string(c['content_with_weight'])<400 for c in children), 'a child too big'
assert all('[S44]' in c['content_with_weight'] for c in children), 'caption lost'
assert all('<td>ישות</td>' in c['content_with_weight'] for c in children), 'header lost'
print('\nALL CHILDREN: small, keep [S44] caption + header row. PASS.')

# edge: empty / no rows
print('no-rows table ->',split_table_into_children({},'<table></table>',False))
