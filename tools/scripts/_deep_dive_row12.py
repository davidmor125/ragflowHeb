"""Deep dive on Row 12: 'האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪'
Gold contains: 'בדוח חריגים מהצהרת לקוח כלולות הפקדות הפקדות מזומן (מט"י+מט"ח) אם מתקיימים כל התנאים הבאים: 1. סכום המינימום של ההפקדות'

Tests:
  1. Does any chunk contain '5,000' or '5000'?
  2. Does any chunk contain 'הפקדות מזומן'?
  3. What does gemma4 actually see in top-12?
  4. Direct ask to gemma4: "Did you see any mention of הפקדות מזומן?"
"""
import sys, json, urllib.request, re
sys.stdout.reconfigure(encoding="utf-8")

T = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
KB = "055ff3d2478b11f180e77faa71318e24"
CHAT = "a7e5d00e478b11f180e77faa71318e24"


def post(path, body):
    req = urllib.request.Request(
        f"http://localhost:9380{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {T}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=300).read().decode("utf-8"))


# Q1: Does the file even contain "הפקדות מזומן" with the limits?
print("=" * 70)
print("TEST 1: search KB for the exact phrase 'הפקדות מזומן' related chunks")
print("=" * 70)
r = post("/api/v1/retrieval", {
    "dataset_ids":[KB],
    "question":"הפקדות מזומן 5000 דוח חריגים",
    "top_k":10,
    "similarity_threshold":0.0,
})
for i, c in enumerate(r["data"]["chunks"][:8]):
    sim = c.get("similarity", 0)
    doc = c.get("document_keyword", "?")
    content = c.get("content", "")
    has_money = "הפקדות מזומן" in content or "הפקדת מזומן" in content
    has_5000 = "5,000" in content or "5000 " in content
    snippet = re.sub(r"\s+", " ", content)[:150]
    print(f"  [{i+1}] sim={sim:.3f}  has_'הפקדות מזומן'={has_money}  has_5000={has_5000}  doc={doc[:30]}")
    print(f"      {snippet}")


# Q2: With the EXACT user question, what does the LLM see?
user_q = "האם בדוח חריגים מול הצהרות לקוח כלולות הפקדות מזומן מעל 5,000 ₪"
print("\n" + "=" * 70)
print(f"TEST 2: user question retrieval, top 12 (what LLM sees)")
print("=" * 70)
r = post("/api/v1/retrieval", {
    "dataset_ids":[KB],
    "question":user_q,
    "top_k":12,
    "similarity_threshold":0.1,
})
chunks = r["data"]["chunks"]
print(f"Got {len(chunks)} chunks back")
for i, c in enumerate(chunks):
    sim = c.get("similarity", 0)
    doc = c.get("document_keyword", "?")
    content = c.get("content", "")
    has_money = "הפקדות מזומן" in content or "הפקדת מזומן" in content
    has_5000 = "5,000" in content or "5000 " in content
    has_dvkach = "דוח חריגים" in content or "חריגים מול" in content
    snippet = re.sub(r"\s+", " ", content)[:200]
    flags = []
    if has_money: flags.append("$$$")
    if has_5000: flags.append("5K")
    if has_dvkach: flags.append("DOCH")
    print(f"  [{i+1}] sim={sim:.3f} {' '.join(flags):12s} {doc[:25]:25s}")
    print(f"      {snippet}")


# Q3: Direct ask to gemma4 with simpler phrasing
print("\n" + "=" * 70)
print("TEST 3: Try asking gemma4 with shorter question")
print("=" * 70)
short_q = "האם הפקדות מזומן נכללות בדוח חריגים מול הצהרות הלקוח?"
print(f"Short question: {short_q}")
body = json.dumps({
    "model":"model",
    "messages":[{"role":"user","content":short_q}],
    "stream":False,
}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(f"http://localhost:9380/api/v1/chats_openai/{CHAT}/chat/completions",
    data=body, method="POST",
    headers={"Authorization": f"Bearer {T}", "Content-Type":"application/json; charset=utf-8"})
r = json.loads(urllib.request.urlopen(req, timeout=600).read().decode("utf-8"))
if "choices" in r:
    print("\nGemma4 answer:")
    print(r["choices"][0]["message"]["content"][:1500])
