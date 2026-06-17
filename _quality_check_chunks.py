"""Quality check the chunks of one parsed doc:
1. No chunk is broken mid-sentence (last char or last 100 chars look like end-of-sentence)
2. Table context preserved (every chunk that has table rows also has the table header)
3. Hebrew quality (lots of Hebrew, no garbled chars)
4. All data captured (compare original file size to sum of chunks)
"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from common import settings as ss
ss.init_settings()
from rag.nlp import search
from api.db.db_models import DB, Document
from bs4 import BeautifulSoup
DB.connect(reuse_if_open=True)

DOC_ID = 'f598a53c46e211f196f633ac796a3d7a'
KB = 'dc0091ca46e211f196f633ac796a3d7a'
TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

doc = Document.get(Document.id == DOC_ID)
print(f"Doc: {doc.name}  size={doc.size}  chunks_in_db={doc.chunk_num}")
print()

# Get all chunks with relevant fields
fields = ['content_with_weight', 'important_kwd', 'doc_type_kwd']
res = ss.docStoreConn.search(fields, [], {'kb_id': KB, 'doc_id': DOC_ID}, [], {}, 0, 500,
                              [search.index_name(TENANT)], [KB])
items_dict = ss.docStoreConn.get_fields(res, fields)
chunks = []
for cid, p in items_dict.items():
    if isinstance(p, dict):
        chunks.append(p)
print(f"Chunks fetched from ES: {len(chunks)}")
print()

# === CHECK 1: Hebrew quality ===
print("="*70)
print("CHECK 1: Hebrew quality")
print("="*70)
heb_total = 0
text_total = 0
for c in chunks:
    text = c.get('content_with_weight','') or ''
    text_total += len(text)
    heb_total += sum(1 for ch in text if 0x590 <= ord(ch) <= 0x5ff)
print(f"  Hebrew chars: {heb_total:,} / {text_total:,} ({heb_total*100//max(text_total,1)}%)")
# Check for garbled — looking for replacement chars or odd patterns
garbled = sum(text.count('�') + text.count('?¿') for c in chunks for text in [c.get('content_with_weight','') or ''])
print(f"  Garbled markers (\\ufffd): {garbled}")
# Sample some hebrew
for c in chunks[:2]:
    text = c.get('content_with_weight','') or ''
    soup = BeautifulSoup(text, 'html.parser')
    visible = soup.get_text()[:200]
    print(f"  Sample visible text: {visible}")
print()

# === CHECK 2: No mid-sentence breaks ===
print("="*70)
print("CHECK 2: Chunk boundaries (not broken mid-sentence)")
print("="*70)
clean_endings = 0
mid_sentence = 0
mid_sentence_examples = []
for c in chunks:
    text = c.get('content_with_weight','') or ''
    if not text.strip():
        continue
    # Strip HTML for end-check
    soup = BeautifulSoup(text, 'html.parser')
    visible = soup.get_text().strip()
    if not visible:
        clean_endings += 1  # pure HTML chunk = ok
        continue
    last_chars = visible[-30:]
    # Clean ending: ends with .!?:;)>,/. or </table> etc.
    if re.search(r'[.״׳!?:;\)\]\}>׃]\s*$', visible) or text.rstrip().endswith(('</table>','</tr>','</td>','</p>','</div>')):
        clean_endings += 1
    else:
        # Check if last chars look like incomplete word
        # If last visible char is a Hebrew/English letter without punctuation → mid-sentence
        if re.search(r'[a-zA-Zא-ת]\s*$', visible):
            mid_sentence += 1
            if len(mid_sentence_examples) < 3:
                mid_sentence_examples.append(visible[-100:])
        else:
            clean_endings += 1
print(f"  Clean endings: {clean_endings}/{len(chunks)} ({clean_endings*100//max(len(chunks),1)}%)")
print(f"  Mid-sentence: {mid_sentence}")
for ex in mid_sentence_examples:
    print(f"    Example tail: '...{ex}'")
print()

# === CHECK 3: Table context preserved ===
print("="*70)
print("CHECK 3: Table context (table chunks should have header rows)")
print("="*70)
table_chunks = 0
table_chunks_with_th = 0
table_chunks_with_caption = 0
table_chunks_no_header = 0
no_header_examples = []
for c in chunks:
    text = c.get('content_with_weight','') or ''
    if '<table>' not in text and '<tr>' not in text:
        continue
    table_chunks += 1
    has_th = '<th' in text  # tag <th> or <thead>
    has_caption = '<caption' in text
    if has_th:
        table_chunks_with_th += 1
    if has_caption:
        table_chunks_with_caption += 1
    if not (has_th or has_caption):
        # may still be ok if it's a single table with no header at all in source
        # but flag as "no header detected"
        table_chunks_no_header += 1
        if len(no_header_examples) < 2:
            no_header_examples.append(text[:300])
print(f"  Total chunks containing tables: {table_chunks}")
print(f"  With <th> (header row):   {table_chunks_with_th}")
print(f"  With <caption>:           {table_chunks_with_caption}")
print(f"  Without any header marker: {table_chunks_no_header}")
print()

# === CHECK 4: Coverage — all data captured ===
print("="*70)
print("CHECK 4: Data coverage")
print("="*70)
total_content_size = sum(len(c.get('content_with_weight','') or '') for c in chunks)
print(f"  Original file size:       {doc.size:,} bytes")
print(f"  Sum of chunks size:       {total_content_size:,} chars")
print(f"  Coverage estimate:        {total_content_size*100//max(doc.size,1)}% (chars vs file bytes — rough)")
# Read original to check Hebrew lines coverage
try:
    bin_data = ss.STORAGE_IMPL.get(doc.kb_id, doc.location)
    if bin_data:
        from rag.nlp import find_codec
        encoding = find_codec(bin_data)
        original_text = bin_data.decode(encoding, errors='ignore')
        soup = BeautifulSoup(original_text, 'html5lib')
        original_visible = soup.get_text()
        original_heb = sum(1 for ch in original_visible if 0x590 <= ord(ch) <= 0x5ff)
        # Sum of visible heb in chunks
        chunks_heb_visible = 0
        for c in chunks:
            text = c.get('content_with_weight','') or ''
            soup_c = BeautifulSoup(text, 'html.parser')
            vis = soup_c.get_text()
            chunks_heb_visible += sum(1 for ch in vis if 0x590 <= ord(ch) <= 0x5ff)
        print(f"  Hebrew chars in original (visible text):  {original_heb:,}")
        print(f"  Hebrew chars in chunks (visible text):    {chunks_heb_visible:,}")
        print(f"  Coverage (Hebrew):                        {chunks_heb_visible*100//max(original_heb,1)}%")
except Exception as e:
    print(f"  (couldn't load original: {e})")
print()

# === CHECK 5: auto_keywords ===
print("="*70)
print("CHECK 5: auto_keywords filled")
print("="*70)
with_kwd = sum(1 for c in chunks if c.get('important_kwd'))
print(f"  Chunks with important_kwd: {with_kwd}/{len(chunks)}")
if with_kwd:
    sample_kwds = [c.get('important_kwd') for c in chunks if c.get('important_kwd')][:5]
    for kw in sample_kwds:
        print(f"    sample: {kw}")
print()

print("="*70)
print("SUMMARY")
print("="*70)
print(f"  Chunks: {len(chunks)}")
print(f"  Avg size: {total_content_size//max(len(chunks),1):,} chars")
print(f"  Sizes range: {min(len(c.get('content_with_weight','') or '') for c in chunks):,}-{max(len(c.get('content_with_weight','') or '') for c in chunks):,}")
print(f"  Hebrew quality: {heb_total*100//max(text_total,1)}%, {garbled} garbled")
print(f"  Clean boundaries: {clean_endings*100//max(len(chunks),1)}%")
print(f"  Table chunks with header: {(table_chunks_with_th+table_chunks_with_caption)*100//max(table_chunks,1)}% of {table_chunks}")
print(f"  auto_keywords: {with_kwd}/{len(chunks)}")
