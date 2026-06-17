"""Run all 132 dataset-aligned questions against the bank-eval dialog
(KB=hozrim). Captures answer, retrieved chunks with rerank scores, and
PASS/FAIL per question. Saves incrementally so a partial run isn't lost."""
import sys, json, time, asyncio, re, csv, os
sys.stdout.reconfigure(encoding='utf-8')

from common import settings as s
s.init_settings()

from api.db.db_models import DB, Dialog
from api.db.services.dialog_service import async_chat
DB.connect(reuse_if_open=True)

DIALOG_ID = "cf68bf1a46f011f196f633ac796a3d7a"   # bank-eval (hozrim KB)
QUESTIONS_FILE = "/ragflow/test_questions_full.json"
OUT_JSON = "/ragflow/eval_full_results.json"
OUT_CSV  = "/ragflow/eval_full_results.csv"

dialog = Dialog.get(Dialog.id == DIALOG_ID)
with open(QUESTIONS_FILE, encoding="utf-8") as f:
    QUESTIONS = json.load(f)

print(f"Dialog:    {dialog.name}")
print(f"LLM:       {dialog.llm_id}")
print(f"Reranker:  {dialog.rerank_id}")
print(f"top_k={dialog.top_k}  top_n={dialog.top_n}  sim_threshold={dialog.similarity_threshold}")
print(f"KB ids:    {dialog.kb_ids}")
print(f"Questions: {len(QUESTIONS)}")
print()

HEB_STOP = {
    "של","על","כן","לא","את","אם","או","גם","כל","יש","זה","זו","זאת","כי","מה","מי","מן","כמו","אך","רק",
    "הוא","היא","אני","אנו","אתה","אתם","אנחנו","אלו","אלה","להיות","ניתן","יכול","צריך","נדרש","כאשר","אשר",
    "פי","תוך","בין","לפי","בעת","אחר","אחרי","לפני","במקרה","כאמור","לבין","אינו","אינה","וכך","כדי","מתוך",
    "בכל","בכך","וכן","כמה","איך","מהם","במהלך",
}

def extract_keywords(gold, k=8):
    if not gold: return []
    cleaned = re.sub(r'[^\w֐-׿\s\d.%]', ' ', gold)
    seen, out = set(), []
    for tok in cleaned.split():
        t = tok.strip().strip('.').strip()
        if len(t) < 3 and not (t.isdigit() or re.fullmatch(r'\d+\.?\d*', t)): continue
        if t in HEB_STOP or t in seen: continue
        seen.add(t); out.append(t)
        if len(out) >= k: break
    return out

def grade(answer, gold):
    if not answer or answer.startswith("[ERROR"):
        return False, "ERROR" if answer else "EMPTY", 0, 0
    clean = re.sub(r'##\d+\$\$', '', answer)
    clean = re.sub(r'\s+', ' ', clean)
    keywords = extract_keywords(gold)
    if not keywords:
        return bool(clean.strip()), "(no-keywords)", 0, 0
    short_gold = (gold or "").strip()
    if len(short_gold) <= 3 and short_gold.lower() in clean.lower():
        return True, short_gold, 1, 1
    hits = [kw for kw in keywords if kw.lower() in clean.lower()]
    threshold = max(1, len(keywords) // 4)
    return (len(hits) >= threshold), (hits[0] if hits else ", ".join(keywords[:3])), len(hits), len(keywords)


async def ask(question):
    messages = [{"role": "user", "content": question}]
    answer, chunks = "", []
    try:
        async for ch in async_chat(dialog, messages, stream=True):
            if not isinstance(ch, dict): continue
            if ch.get("answer"): answer = ch["answer"]
            ref = ch.get("reference") or {}
            if ref.get("chunks"): chunks = ref["chunks"]
    except Exception as e:
        return f"[ERROR: {type(e).__name__}: {e}]", []
    return answer, chunks


def rank_of(chunks, proc):
    needle = f"{proc}.html"
    rk, score = 0, None
    for i, ck in enumerate(chunks, 1):
        nm = ck.get("docnm_kwd") or ""
        if nm.endswith(needle) or os.path.basename(nm).startswith(proc):
            rk = i; score = ck.get("similarity"); break
    return {
        "found": rk > 0, "rank": rk,
        "top_score": chunks[0].get("similarity") if chunks else None,
        "matched_score": score,
        "total_chunks": len(chunks),
    }


def save(results, summary):
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#","שורת אקסל","פרוצדורה","נושא","תת-נושא","שאלה",
                    "תשובה צפויה","תשובת המערכת",
                    "תשובה PASS/FAIL","מילות מפתח שהותאמו",
                    "רירנקר PASS/FAIL","דירוג קובץ נכון","ציון רירנקר","ציון top",
                    "סה\"כ צ'אנקים","זמן (שנ')"])
        for r in results:
            w.writerow([
                r["n"], r["row"], r["procedure"], r["topic"], r["subtopic"], r["question"],
                r["expected_answer"], r["system_answer"],
                "PASS" if r["passed"] else "FAIL",
                f'{r["keyword_hits"]}/{r["keywords_total"]}',
                "PASS" if r["rerank_correct_doc_found"] else "FAIL",
                r["rerank_rank_of_correct_doc"] or "-",
                f'{r["rerank_score_of_correct_doc"]:.3f}' if r["rerank_score_of_correct_doc"] is not None else "-",
                f'{r["rerank_top_score"]:.3f}' if r["rerank_top_score"] is not None else "-",
                r["rerank_total_chunks"], r["elapsed_sec"],
            ])


async def main():
    results = []
    answer_pass, rerank_top1, rerank_top3, rerank_found = 0, 0, 0, 0

    t_start = time.time()
    for i, q in enumerate(QUESTIONS, 1):
        question = q["question"]; expected = q["expected_answer"]; proc = q["procedure"]
        t0 = time.time()
        answer, chunks = await ask(question)
        elapsed = time.time() - t0

        ok, match_info, hits, total_kw = grade(answer, expected)
        rk = rank_of(chunks, proc)

        if ok:                  answer_pass += 1
        if rk["found"]:         rerank_found += 1
        if rk["rank"] == 1:     rerank_top1 += 1
        if 1 <= rk["rank"] <= 3:rerank_top3 += 1

        ans_short = (answer or "")[:100].replace("\n", " ")
        ok_str = '✅' if ok else '❌'
        rer_str = f"r#{rk['rank']}" if rk["found"] else "MISS"
        elapsed_total = time.time() - t_start
        eta_sec = elapsed_total * (len(QUESTIONS) - i) / i
        print(f"[{i:>3}/{len(QUESTIONS)}] {ok_str} {rer_str:5} {elapsed:>5.1f}s  proc={proc:>5}  {question[:70]}")
        if not ok:
            print(f"           A: {ans_short}")

        results.append({
            "n": i, "row": q["row"], "procedure": proc,
            "topic": q["topic"], "subtopic": q["subtopic"],
            "question": question,
            "expected_answer": expected,
            "system_answer": answer,
            "passed": ok, "match_info": match_info,
            "keyword_hits": hits, "keywords_total": total_kw,
            "elapsed_sec": round(elapsed, 2),
            "rerank_correct_doc_found": rk["found"],
            "rerank_rank_of_correct_doc": rk["rank"],
            "rerank_score_of_correct_doc": rk["matched_score"],
            "rerank_top_score": rk["top_score"],
            "rerank_total_chunks": rk["total_chunks"],
            "retrieved_top5": [
                {
                    "docnm": c.get("docnm_kwd"),
                    "similarity": c.get("similarity"),
                    "vector_similarity": c.get("vector_similarity"),
                    "term_similarity": c.get("term_similarity"),
                    "snippet": (c.get("content_with_weight") or "")[:200],
                }
                for c in chunks[:5]
            ],
        })

        summary = {
            "answer_pass": answer_pass, "rerank_top1": rerank_top1,
            "rerank_top3": rerank_top3, "rerank_found": rerank_found,
            "total": len(results),
            "elapsed_total_sec": round(elapsed_total, 1),
        }
        save(results, summary)

    n = len(results)
    print()
    print("=" * 78)
    print(f"FINAL  ({n} questions, total {time.time() - t_start:.0f}s)")
    print("=" * 78)
    print(f"  Answers correct:                                 {answer_pass}/{n}  ({100*answer_pass//n}%)")
    print(f"  Rerank — correct doc anywhere in top-{dialog.top_n}:        {rerank_found}/{n}  ({100*rerank_found//n}%)")
    print(f"  Rerank — correct doc at rank #1:                  {rerank_top1}/{n}  ({100*rerank_top1//n}%)")
    print(f"  Rerank — correct doc in top-3:                    {rerank_top3}/{n}  ({100*rerank_top3//n}%)")

asyncio.run(main())
