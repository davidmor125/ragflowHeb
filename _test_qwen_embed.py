import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')
OLLAMA='http://localhost:11434/api/embeddings'

def embed(txt):
    r=requests.post(OLLAMA,json={'model':'qwen3-embedding:4b','prompt':txt},timeout=180)
    return r.status_code, r.json()

# 1. basic Hebrew + dimension
code,j=embed('בדיקת עברית למודל הטמעה Qwen3')
dim=len(j.get('embedding',[])) if code==200 else 0
print(f'basic Hebrew: status={code} dim={dim}')

# 2. THE critical test: does it handle long Hebrew (where bge-m3 crashed at ~3000)?
heb='זהו טקסט עברי ארוך לבדיקת אורך ההקשר של מודל ההטמעה החדש. '
for n in [100,200,300,400,600,800]:
    txt=heb*n
    cl=len(enc.encode(txt))
    code,j=embed(txt)
    ok = code==200 and 'embedding' in j
    print(f'  repeats={n:4d} cl100k_tokens={cl:5d} status={code} ok={ok}'+('' if ok else f' ERR={str(j)[:80]}'))
