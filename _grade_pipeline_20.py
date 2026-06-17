"""Show me each pipeline answer next to its gold for manual reading.
Trim the 'thinking-leak' if any, take only the last cohesive Hebrew chunk.
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

with open('eval_pipeline_20.json', encoding='utf-8') as f:
    d = json.load(f)

def final_hebrew(text):
    """Take last 1500 chars after the last 'Final' marker, or just last Hebrew run."""
    if not text: return ''
    # Strip <think>
    out = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # If output has 'Final ...:' or '*Final ' keyword, take from after it
    m = list(re.finditer(r'\*?Final[^:*\n]*?:?\*?\s*\n', out))
    if m:
        out = out[m[-1].end():]
    # Trim leading/trailing whitespace
    out = out.strip()
    # If still huge, last 2000 chars
    if len(out) > 2000:
        out = out[-2000:]
    return out

for r in d['results']:
    print('━' * 100)
    print(f"n={r['n']:>3}  proc={r['procedure']:>5}  prev_kw={r['old_kw_passed']}  prev_llm={r['old_llm_verdict']}  elapsed={r['pipeline_elapsed_s']}s  raw_len={len(r['pipeline_answer_raw'])}")
    print(f"Q: {r['question']}")
    print(f"GOLD: {(r['gold'] or '')[:400]}")
    print()
    h = final_hebrew(r['pipeline_answer_raw'])
    print(f"PIPELINE ANSWER (final {len(h)}c):")
    print(h[:1500])
    print()
