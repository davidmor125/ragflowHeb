"""AI-judge eval for the chap-1(1).pdf dialog (pdf-eval)."""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
import _eval_ai_judge as E

E.CHAT_ID = '1c40d2d8657c11f19d1425719d627201'  # pdf-eval dialog

QFILE = sys.argv[1] if len(sys.argv) > 1 else '_pdf_test_questions.json'
OUTFILE = sys.argv[2] if len(sys.argv) > 2 else '_pdf_eval_results.json'
questions = json.load(open(QFILE, encoding='utf-8'))
print(f'PDF eval: {len(questions)} questions | judge={E.JUDGE_MODEL}', flush=True)

results, counts = [], {'correct': 0, 'partial': 0, 'wrong': 0, 'invalid_question': 0, 'error': 0}
for i, item in enumerate(questions):
    q = item['question']
    t0 = time.time()
    try:
        sid = E.create_session(f'pdf-eval-{int(time.time()*1000)}')
        answer, nch = E.ask(q, sid)
    except Exception as e:
        answer, nch = f'[ASK-ERR {type(e).__name__}: {e}]', 0
    t_ans = time.time() - t0
    try:
        verdict, reason = E.judge(q, item['expected_answer'], answer)
    except Exception as e:
        try:
            verdict, reason = E.judge(q, item['expected_answer'], answer, model=E.JUDGE_FALLBACK)
        except Exception as e2:
            verdict, reason = 'error', f'{type(e).__name__} / {type(e2).__name__}'
    counts[verdict] = counts.get(verdict, 0) + 1
    results.append({**item, 'answer': answer, 'chunks': nch, 'verdict': verdict, 'reason': reason,
                    'ans_sec': round(t_ans, 1)})
    print(f"[{i+1}/{len(questions)}] p{item['page']} {'TBL ' if item['is_table'] else ''}{verdict.upper():8s} ({t_ans:.0f}s) | {reason[:80]}", flush=True)
    json.dump({'counts': counts, 'results': results}, open(OUTFILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

valid = len(questions) - counts['invalid_question'] - counts['error']
print('=' * 60)
print(f"PDF FINAL: correct={counts['correct']} partial={counts['partial']} wrong={counts['wrong']} invalid={counts['invalid_question']} err={counts['error']}")
print(f"strict: {100*counts['correct']/max(valid,1):.0f}% | +partial: {100*(counts['correct']+counts['partial'])/max(valid,1):.0f}%")
