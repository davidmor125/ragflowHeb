"""Output ONLY the final Hebrew answer, written to UTF-8 file."""
import json, re, io, sys

with open('eval_pipeline_v2_20.json', encoding='utf-8') as f:
    d = json.load(f)

def get_final_answer(text):
    """gemma4:26b duplicates the final answer at the very end after all thinking.
    Strategy: take the last 1500 chars and clean up obvious thinking-leftovers.
    """
    if not text: return ''
    # Take only the very tail
    tail = text[-1500:]
    # Remove leading thinking lines (lines starting with '*' or 'Wait' or 'Final')
    lines = tail.split('\n')
    # Find first line that looks like 'real answer' (long Hebrew, no '*' or 'Wait' or 'Self-Correction')
    cleaned = []
    started = False
    for ln in lines:
        ln_strip = ln.strip()
        is_thinking = (
            ln_strip.startswith('*') or
            ln_strip.startswith('Wait') or
            ln_strip.startswith('Self-Correction') or
            ln_strip.startswith('Final ') or
            'check' in ln_strip.lower()[:20] or
            (len(ln_strip) > 0 and 'a'<=ln_strip[0].lower()<='z')
        )
        heb = sum(1 for c in ln_strip if 0x590<=ord(c)<=0x5ff)
        if heb > 5 and not is_thinking:
            started = True
        if started:
            cleaned.append(ln)
    return '\n'.join(cleaned).strip()

with open('_clean_v2.txt', 'w', encoding='utf-8') as out:
    for r in d['results']:
        out.write('='*100 + '\n')
        out.write(f"n={r['n']:>3}  proc={r['procedure']:>5}  prev_kw={r['old_kw_passed']}  v2_time={r['elapsed_s']}s\n")
        out.write(f"Q: {r['question']}\n")
        out.write(f"GOLD: {(r['gold'] or '')[:300]}\n\n")
        ans = get_final_answer(r['pipeline_v2_answer'])
        out.write(f"V2 FINAL ANSWER:\n{ans}\n\n")

print("done")
