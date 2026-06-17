"""Read each completed v2 answer, extract final Hebrew block, show alongside gold."""
import json, re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('eval_pipeline_v2_20.json', encoding='utf-8') as f:
    d = json.load(f)

def final_hebrew(text):
    if not text: return ''
    out = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # remove the entire English thinking block before Hebrew block
    # simple approach: find last 'תשובה' or 'Final' and take from there
    # Or: find the longest contiguous Hebrew-rich tail
    # Simple: look for repeated final-block (gemma writes the answer twice)
    m = list(re.finditer(r'\*Final[^:*\n]*?:?\*?\s*\n', out))
    if m:
        out = out[m[-1].end():]
    out = out.strip()
    # If still has English, take last block of >=200 contiguous Hebrew-rich text
    if len(out) > 1500:
        out = out[-1500:]
    return out

for r in d['results']:
    print('=' * 110)
    print(f"n={r['n']:>3}  proc={r['procedure']:>5}  prev_kw={r['old_kw_passed']}  v2={r['elapsed_s']}s")
    print(f"Q: {r['question']}")
    print(f"GOLD: {(r['gold'] or '')[:350]}")
    print()
    h = final_hebrew(r['pipeline_v2_answer'])
    print(f"V2 ANSWER (last {len(h)} chars):")
    print(h)
    print()
