"""Generate 50 gold Q&A pairs from chap-1(1).pdf chunks using gpt-oss:120b-cloud."""
import sys, json, requests
sys.stdout.reconfigure(encoding='utf-8')

OLLAMA = 'http://localhost:11434/api/chat'
MODEL = 'gpt-oss:120b-cloud'
TARGET = 50

d = json.load(open('_audit_pdf_chunks.json', encoding='utf-8'))
hits = d['hits']['hits']

def heb_ratio(s):
    return sum(1 for c in s if '֐' <= c <= '׿') / max(len(s), 1)

# all usable chunks: enough text, mostly Hebrew OR a table
srcs = [h['_source'] for h in hits]
tables = [s for s in srcs if '<table' in s['content_with_weight'].lower()]
texts = [s for s in srcs if s not in tables and len(s['content_with_weight']) > 350 and heb_ratio(s['content_with_weight']) > 0.35]
texts.sort(key=lambda s: s.get('page_num_int', [0])[0] if s.get('page_num_int') else 0)
selected = (tables + texts)[:TARGET]
print(f'{len(srcs)} chunks total -> {len(selected)} selected ({len(tables)} tables)')

SYS = """אתה מחבר שאלות בוחן למערכת RAG. תקבל קטע מתוך דוח בנק ישראל.
חבר שאלה אחת עניינית שניתן לענות עליה אך ורק מתוך הקטע, ותשובת זהב מדויקת ותמציתית מתוך הקטע.
כללים:
- השאלה והתשובה חייבות להיות בעברית בלבד. אסור לכתוב באנגלית.
- השאלה חייבת לעמוד בפני עצמה (בלי "לפי הקטע", בלי הפניות לקטע).
- השאלה צריכה להיות ספציפית מספיק כדי שמי שמחפש במסמך ימצא את הקטע הזה.
- העדף שאלות על עובדות, מספרים, סיבות ומנגנונים.
- תשובת הזהב: 1-4 משפטים, רק עובדות שמופיעות בקטע.
החזר JSON בלבד: {"question": "...", "gold_answer": "..."}"""

out = []
for i, s in enumerate(selected):
    content = s['content_with_weight'][:4000]
    body = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYS},
            {'role': 'user', 'content': f'הקטע (עמוד {s.get("page_num_int",["?"])[0]}):\n{content}'},
        ],
        'stream': False, 'format': 'json', 'options': {'temperature': 0.3},
    }
    try:
        r = requests.post(OLLAMA, json=body, timeout=180)
        v = json.loads(r.json()['message']['content'])
        if not v.get('question') or not v.get('gold_answer'):
            raise ValueError('empty fields')
        out.append({
            'row': len(out) + 1,
            'page': s.get('page_num_int', ['?'])[0],
            'is_table': '<table' in content.lower(),
            'question': v['question'],
            'expected_answer': v['gold_answer'],
        })
        print(f"[{len(out)}/{TARGET}] p{out[-1]['page']} {'TBL ' if out[-1]['is_table'] else ''}{v['question'][:80]}", flush=True)
    except Exception as e:
        print(f'[chunk {i}] FAILED: {type(e).__name__}: {e}', flush=True)
    json.dump(out, open('_pdf_test_questions_50.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print(f'\nsaved {len(out)} questions to _pdf_test_questions_50.json')
