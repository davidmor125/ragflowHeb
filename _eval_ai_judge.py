"""
AI-as-a-Judge evaluation of the bank-eval RAG dialog.

For each sampled question:
  1. Ask through the RAGFlow dialog (new session per question).
  2. Judge the answer against the gold expected_answer using gpt-oss:120b-cloud
     (via local Ollama API) returning a strict JSON verdict.

Usage:
  python _eval_ai_judge.py [--out FILE] [--sample N] [--all]
"""
import sys, os, json, time, argparse, re
sys.stdout.reconfigure(encoding='utf-8')
import requests

BASE_URL = 'http://localhost:9380'
API = f'{BASE_URL}/api/v1'
KEY = 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
CHAT_ID = 'cf68bf1a46f011f196f633ac796a3d7a'   # bank-eval dialog
H = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}

OLLAMA = 'http://localhost:11434/api/chat'
JUDGE_MODEL = 'gpt-oss:120b-cloud'
JUDGE_FALLBACK = 'gemma4:26b'

JUDGE_SYSTEM = """אתה שופט קפדני המעריך תשובות של מערכת RAG על נהלים בנקאיים.
תקבל: שאלה, תשובת זהב (מהנוהל הרשמי), ותשובת המערכת.
קבע פסק דין:
- "correct" — תשובת המערכת מכילה את העובדות המרכזיות מתשובת הזהב הרלוונטיות לשאלה, ללא סתירות מהותיות. ניסוח שונה, סדר שונה או פירוט נוסף נכון — עדיין correct.
- "partial" — חלק מהעובדות המרכזיות נמצאות, אך חסר רכיב מהותי שהשאלה דורשת.
- "wrong" — התשובה סותרת את הזהב, ממציאה עובדות, לא רלוונטית, או ריקה/שגיאה.
אם תשובת הזהב עצמה לא עונה על השאלה (שאלה פגומה) — קבע "invalid_question".
החזר JSON בלבד: {"verdict": "...", "reason": "משפט אחד בעברית"}"""


def create_session(name):
    r = requests.post(f'{API}/chats/{CHAT_ID}/sessions', json={'name': name}, headers=H, timeout=30)
    j = r.json()
    if j.get('code') != 0:
        raise RuntimeError(f'create_session failed: {j}')
    return j['data']['id']


def ask(question, session_id, timeout=300):
    body = {'question': question, 'stream': False, 'session_id': session_id}
    r = requests.post(f'{API}/chats/{CHAT_ID}/completions', json=body, headers=H, timeout=timeout)
    if r.status_code != 200:
        return f'[HTTP {r.status_code}]', 0
    try:
        j = r.json()
        if j.get('code') == 0 and isinstance(j.get('data'), dict):
            ref = j['data'].get('reference') or {}
            nch = len(ref.get('chunks', [])) if isinstance(ref, dict) else 0
            return j['data'].get('answer', ''), nch
    except ValueError:
        pass
    answer, nch = '', 0
    for line in r.text.splitlines():
        line = line.strip()
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if payload in ('', '[DONE]'):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        data = obj.get('data')
        if isinstance(data, dict):
            if isinstance(data.get('answer'), str) and data['answer']:
                answer = data['answer']
            ref = data.get('reference')
            if isinstance(ref, dict) and ref.get('chunks'):
                nch = len(ref['chunks'])
    return answer, nch


def judge(question, gold, answer, model=JUDGE_MODEL):
    clean = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
    clean = re.sub(r'##\d+\$\$', '', clean).strip()
    user = f"""שאלה: {question}

תשובת זהב (מהנוהל):
{gold}

תשובת המערכת:
{clean[:6000]}"""
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': JUDGE_SYSTEM},
            {'role': 'user', 'content': user},
        ],
        'stream': False,
        'format': 'json',
        'options': {'temperature': 0},
    }
    r = requests.post(OLLAMA, json=body, timeout=180)
    r.raise_for_status()
    content = r.json()['message']['content']
    v = json.loads(content)
    verdict = v.get('verdict', 'wrong')
    if verdict not in ('correct', 'partial', 'wrong', 'invalid_question'):
        verdict = 'wrong'
    return verdict, v.get('reason', '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='_eval_judge_results.json')
    ap.add_argument('--sample', type=int, default=4, help='take every Nth question')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    questions = json.load(open('test_questions_full.json', encoding='utf-8'))
    sample = questions if args.all else questions[::args.sample]
    print(f'Evaluating {len(sample)} questions | judge={JUDGE_MODEL}', flush=True)

    results, counts = [], {'correct': 0, 'partial': 0, 'wrong': 0, 'invalid_question': 0, 'error': 0}
    t_start = time.time()
    for i, item in enumerate(sample):
        q = item['question']
        t0 = time.time()
        try:
            sid = create_session(f'judge-eval-{int(time.time()*1000)}')
            answer, nch = ask(q, sid)
        except Exception as e:
            answer, nch = f'[ASK-ERR {type(e).__name__}: {e}]', 0
        t_ans = time.time() - t0
        t0 = time.time()
        try:
            verdict, reason = judge(q, item['expected_answer'], answer)
        except Exception as e:
            try:
                verdict, reason = judge(q, item['expected_answer'], answer, model=JUDGE_FALLBACK)
                reason = f'[fallback-judge] {reason}'
            except Exception as e2:
                verdict, reason = 'error', f'{type(e).__name__}: {e} | fallback: {type(e2).__name__}'
        t_jdg = time.time() - t0
        counts[verdict] = counts.get(verdict, 0) + 1
        results.append({
            'row': item['row'], 'procedure': item['procedure'], 'question': q,
            'answer': answer, 'chunks': nch, 'verdict': verdict, 'reason': reason,
            'ans_sec': round(t_ans, 1), 'judge_sec': round(t_jdg, 1),
        })
        done = i + 1
        valid = done - counts['invalid_question'] - counts['error']
        acc = 100 * counts['correct'] / max(valid, 1)
        acc_p = 100 * (counts['correct'] + counts['partial']) / max(valid, 1)
        print(f"[{done}/{len(sample)}] row={item['row']} {verdict.upper():8s} ({t_ans:.0f}s+{t_jdg:.0f}s) "
              f"| acc={acc:.0f}% (+partial={acc_p:.0f}%) | {reason[:90]}", flush=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'counts': counts, 'n': done, 'results': results}, f, ensure_ascii=False, indent=1)

    total_min = (time.time() - t_start) / 60
    valid = len(sample) - counts['invalid_question'] - counts['error']
    print('=' * 70)
    print(f"FINAL: correct={counts['correct']} partial={counts['partial']} wrong={counts['wrong']} "
          f"invalid={counts['invalid_question']} error={counts['error']}")
    print(f"Accuracy (strict, valid only): {100*counts['correct']/max(valid,1):.1f}%")
    print(f"Accuracy (correct+partial):    {100*(counts['correct']+counts['partial'])/max(valid,1):.1f}%")
    print(f"Took {total_min:.1f} min. Saved {args.out}")


if __name__ == '__main__':
    main()
