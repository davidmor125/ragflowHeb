"""
Re-parse 32904.html (ביטול כרטיסי אשראי) in the 'hozrim' KB,
then ask the 5 credit-cards questions through the 'bank-eval' Dialog.

Uses HTTP API only (no internal imports).
"""
import sys, os, time, json, re
sys.stdout.reconfigure(encoding='utf-8')
import requests
import pymysql

# ---- Config ----
BASE_URL = os.environ.get('RAGFLOW_BASE_URL', 'http://localhost:9380')
API_KEY  = os.environ.get('RAGFLOW_API_KEY', 'ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI')
KB_ID    = 'dc0091ca46e211f196f633ac796a3d7a'           # hozrim
DOC_ID   = 'f84ca83246e211f196f633ac796a3d7a'           # טסט/32904.html
CHAT_ID  = 'cf68bf1a46f011f196f633ac796a3d7a'           # bank-eval Dialog
TENANT   = '2507563a42bd11f1a6bba9e87ac7a32c'
PARSE_TIMEOUT_SEC = 30 * 60
PER_Q_TIMEOUT_SEC = 5 * 60

API = f"{BASE_URL}/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ---- 5 questions on procedure 32904 (rows 68-72 in test_questions_full.json) ----
QUESTIONS = [
    {
        "n": 68,
        "q": "איך ניתן לבטל כרטיס אשראי בהתכתבות עם בנקאי?",
        "expected": [
            "ביטול כרטיס", "התכתבות", "בנקאי", "טלפונית", "שימור", "מועדונים", "32919",
        ],
    },
    {
        "n": 69,
        "q": "איך ניתן לבטל כרטיס מסוג ויזה כאל?",
        "expected": [
            "חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות",
        ],
    },
    {
        "n": 70,
        "q": "איך ניתן לבטל כרטיס של ישראכרט?",
        "expected": [
            "חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות",
        ],
    },
    {
        "n": 71,
        "q": "איך מבטלים כרטיס אשראי מסוג מקס?",
        "expected": [
            "חוק שירותי תשלום", "ביטול כרטיס בהודעה", "פרונטלית", "טלפונית", "התכתבות",
        ],
    },
    {
        "n": 72,
        "q": "כמה עולה לבטל כרטיס אשראי?",
        "expected": [
            "ריכוז תעריפוני", "תעריפון", "עמלות",
        ],
    },
]

# ---- DB helper for monitoring parse progress ----
def _db_cur():
    conn = pymysql.connect(host='localhost', port=3306, user='root',
                            password='infini_rag_flow', database='rag_flow',
                            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    return conn, conn.cursor()


def doc_status(doc_id):
    conn, cur = _db_cur()
    try:
        cur.execute("SELECT id, name, run, progress, progress_msg, chunk_num FROM document WHERE id=%s", (doc_id,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()


# ---- Step 1: trigger parse via HTTP (use legacy /v1/document/run with delete=true) ----
def trigger_parse():
    print(f"[1/3] Triggering re-parse on doc {DOC_ID} in KB {KB_ID}...", flush=True)
    url = f"{BASE_URL}/v1/document/run"
    body = {"doc_ids": [DOC_ID], "run": "1", "delete": True}
    r = requests.post(url, json=body, headers=HEADERS, timeout=30)
    print(f"     HTTP {r.status_code}: {r.text[:300]}", flush=True)
    if r.status_code != 200:
        raise SystemExit(f"Parse trigger failed: {r.status_code} {r.text}")
    j = r.json()
    if j.get('code') not in (0, None):
        raise SystemExit(f"Parse trigger error: {j}")
    print("     parse triggered (delete=true to force re-chunk).\n", flush=True)


# ---- Step 2: poll DB for parse completion ----
def wait_for_parse():
    print(f"[2/3] Polling parse progress (timeout {PARSE_TIMEOUT_SEC}s)...", flush=True)
    t0 = time.time()
    last_msg = None
    while time.time() - t0 < PARSE_TIMEOUT_SEC:
        d = doc_status(DOC_ID)
        if not d:
            raise SystemExit("Doc disappeared from DB!")
        msg = (d.get('progress_msg') or '').strip()
        last_line = msg.split('\n')[-1] if msg else ''
        if last_line != last_msg:
            elapsed = int(time.time() - t0)
            print(f"     [{elapsed:4d}s] run={d['run']}  progress={d['progress']:.2f}  chunks={d['chunk_num']}  | {last_line[:120]}", flush=True)
            last_msg = last_line
        run = str(d.get('run'))
        if run == '3':
            print(f"     ✅ parse done. final chunks={d['chunk_num']}\n", flush=True)
            return d
        if run == '4':
            print(f"     ❌ parse FAILED. msg:\n{msg}", flush=True)
            raise SystemExit("Parse failed (run=4)")
        time.sleep(8)
    raise SystemExit(f"Parse timeout after {PARSE_TIMEOUT_SEC}s")


# ---- Step 3: ask 5 questions via Dialog ----
def create_session(name):
    r = requests.post(f"{API}/chats/{CHAT_ID}/sessions", json={"name": name}, headers=HEADERS, timeout=30)
    j = r.json()
    if j.get('code') != 0:
        raise SystemExit(f"create_session failed: {j}")
    return j['data']['id']


def ask(question, session_id):
    """Use streaming=False - a single JSON response with the full answer."""
    body = {"question": question, "stream": False, "session_id": session_id}
    r = requests.post(f"{API}/chats/{CHAT_ID}/completions", json=body,
                      headers=HEADERS, timeout=PER_Q_TIMEOUT_SEC, stream=False)
    if r.status_code != 200:
        return f"[HTTP {r.status_code}: {r.text[:200]}]", None
    # The completions endpoint always streams (server-side decision regardless of `stream`),
    # so we may receive SSE-like text. Try JSON first; fall back to SSE parse.
    text = r.text
    try:
        j = r.json()
        if j.get('code') == 0 and isinstance(j.get('data'), dict):
            return j['data'].get('answer', ''), j['data'].get('reference', {})
    except ValueError:
        pass
    # SSE parse: take last data: line with answer
    answer = ""
    reference = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('data:'):
            continue
        payload = line[len('data:'):].strip()
        if payload in ('', '[DONE]'):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        data = obj.get('data')
        if isinstance(data, dict):
            ans = data.get('answer')
            if isinstance(ans, str) and ans:
                answer = ans  # last one wins (final cumulative)
            ref = data.get('reference')
            if isinstance(ref, dict) and ref:
                reference = ref
    return answer, reference


def grade(answer, expected_kws):
    if not answer or len(answer.strip()) < 5:
        return False, "EMPTY"
    clean = re.sub(r'##\d+\$\$', '', answer)
    clean = re.sub(r'<think>.*?</think>', '', clean, flags=re.DOTALL)
    clean = re.sub(r'\s+', ' ', clean).lower()
    hit = []
    for kw in expected_kws:
        if kw.lower() in clean:
            hit.append(kw)
    # Pass if at least 2 keywords or 60% of expected appear
    threshold = max(2, int(0.5 * len(expected_kws)))
    return (len(hit) >= threshold), hit


def run_questions():
    print(f"[3/3] Asking {len(QUESTIONS)} questions via dialog '{CHAT_ID}'...", flush=True)
    sid = create_session("credit-cards-test-" + str(int(time.time())))
    print(f"     session_id={sid}\n", flush=True)
    results = []
    pass_count = 0
    for q in QUESTIONS:
        print(f"--- Q{q['n']}: {q['q']} ---", flush=True)
        t0 = time.time()
        try:
            answer, ref = ask(q['q'], sid)
        except Exception as e:
            answer, ref = f"[ERR: {type(e).__name__}: {e}]", {}
        elapsed = time.time() - t0
        ok, hit = grade(answer, q['expected'])
        if ok:
            pass_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        ans_show = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)[:600]
        chunks_used = len((ref or {}).get('chunks', [])) if isinstance(ref, dict) else 0
        print(f"  {status}  ({elapsed:.1f}s)  hit={hit}  chunks_retrieved={chunks_used}", flush=True)
        print(f"  Answer (first 600 chars):\n  {ans_show}\n", flush=True)
        results.append({
            "n": q['n'], "question": q['q'], "expected": q['expected'],
            "answer": answer, "passed": ok, "hit_keywords": hit,
            "elapsed_sec": round(elapsed, 1), "chunks_retrieved": chunks_used,
        })
        with open('test_credit_cards_results.json', 'w', encoding='utf-8') as f:
            json.dump({"pass": pass_count, "total": len(QUESTIONS), "results": results}, f, ensure_ascii=False, indent=2)

    print("=" * 70, flush=True)
    print(f"FINAL: {pass_count}/{len(QUESTIONS)} passed ({100*pass_count//len(QUESTIONS)}%)", flush=True)
    print(f"Saved to test_credit_cards_results.json", flush=True)
    print("=" * 70, flush=True)


if __name__ == '__main__':
    print(f"=== Credit Cards Test ===", flush=True)
    print(f"  KB        : hozrim ({KB_ID})", flush=True)
    print(f"  Doc       : טסט/32904.html ({DOC_ID})", flush=True)
    print(f"  Dialog    : bank-eval ({CHAT_ID})", flush=True)
    print(f"  Base URL  : {BASE_URL}", flush=True)
    print(f"  Questions : {len(QUESTIONS)}\n", flush=True)

    pre = doc_status(DOC_ID)
    print(f"  Pre-parse: run={pre['run']} progress={pre['progress']} chunks={pre['chunk_num']}\n", flush=True)

    if os.environ.get('SKIP_PARSE') != '1':
        trigger_parse()
        wait_for_parse()
    else:
        print("  [SKIP_PARSE=1] using existing chunks\n", flush=True)
    run_questions()
