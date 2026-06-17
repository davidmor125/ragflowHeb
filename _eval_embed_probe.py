import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import requests, tiktoken
enc=tiktoken.get_encoding('cl100k_base')

# Ollama is reachable from host on 11434 (container uses host.docker.internal)
OLLAMA='http://localhost:11434/api/embeddings'
heb='זהו טקסט עברי לבדיקת אורך ההקשר של מודל ההטמעה. '  # ~ repeats
def probe(n_repeat):
    txt=heb*n_repeat
    cl=len(enc.encode(txt))
    try:
        r=requests.post(OLLAMA,json={'model':'bge-m3','prompt':txt},timeout=120)
        ok = r.status_code==200 and 'embedding' in r.json()
        return cl,len(txt),r.status_code,ok,(r.text[:120] if not ok else '')
    except Exception as e:
        return cl,len(txt),'ERR',False,str(e)[:120]

for n in [50,100,150,200,250,300,350,400,500]:
    cl,chars,code,ok,err=probe(n)
    print(f'repeats={n:4d} chars={chars:6d} cl100k_tokens={cl:5d} status={code} ok={ok} {err}')

print('\n--- bisect the cl100k token cutoff for Hebrew ---')
lo,hi=100,150
while hi-lo>2:
    mid=(lo+hi)//2
    cl,chars,code,ok,err=probe(mid)
    print(f'  repeats={mid} cl100k={cl} ok={ok}')
    if ok: lo=mid
    else: hi=mid
print(f'CUTOFF between repeats {lo} and {hi}  (~{lo*48}-{hi*48} chars, ~{lo*48}-{hi*48} cl100k tokens for this filler)')
