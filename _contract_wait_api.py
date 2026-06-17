import sys, time
sys.stdout.reconfigure(encoding='utf-8')
import requests
BASE='http://localhost:9380/api/v1'
KEY='ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI'
H={'Authorization':f'Bearer {KEY}'}
t0=time.time()
while time.time()-t0 < 180:
    try:
        r=requests.get(f'{BASE}/datasets?page=1&page_size=1',headers=H,timeout=5)
        if r.status_code==200 and r.json().get('code')==0:
            print(f'API UP after {time.time()-t0:.0f}s')
            sys.exit(0)
        print('status',r.status_code)
    except Exception as e:
        pass
    time.sleep(5)
print('API NOT UP in 180s'); sys.exit(1)
