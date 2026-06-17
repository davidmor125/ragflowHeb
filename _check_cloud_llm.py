"""Check if gpt-oss:120b-cloud is back online."""
import sys, asyncio, time
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
from common import settings as s
s.init_settings()
from api.db.db_models import DB
from api.db.services.llm_service import LLMBundle
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from common.constants import LLMType
DB.connect(reuse_if_open=True)

TENANT = '2507563a42bd11f1a6bba9e87ac7a32c'

async def test_model(name):
    print(f"\n=== Testing {name} ===", flush=True)
    try:
        mc = get_model_config_by_type_and_name(TENANT, LLMType.CHAT, name)
        mdl = LLMBundle(TENANT, mc)
        t0 = time.time()
        ans = await asyncio.wait_for(
            mdl.async_chat("You are a helpful assistant.",
                           [{"role":"user","content":"שלום, מה שלומך? ענה במילה אחת בעברית."}],
                           {"temperature": 0.0, "max_tokens": 50}),
            timeout=60
        )
        if isinstance(ans, tuple):
            ans = ans[0]
        elapsed = time.time() - t0
        print(f"  ✅ OK in {elapsed:.1f}s. Answer: {ans[:200]}", flush=True)
        return True
    except asyncio.TimeoutError:
        print(f"  ❌ TIMEOUT after 60s", flush=True)
        return False
    except Exception as e:
        msg = str(e)[:300]
        if "weekly usage" in msg or "rate" in msg.lower():
            print(f"  ❌ QUOTA/RATE ERROR: {msg}", flush=True)
        else:
            print(f"  ❌ ERROR: {type(e).__name__}: {msg}", flush=True)
        return False

async def main():
    for name in ['gpt-oss:120b-cloud@Ollama', 'gemma4:31b-cloud@Ollama']:
        await test_model(name)

asyncio.run(main())
