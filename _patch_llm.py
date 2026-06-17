"""Insert debug prints into llm.py inside the container, then restore later."""
import re

with open('/ragflow/agent/component/llm.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Insert debug after `vars = self.get_input_elements() if not self._param.debug_inputs else self._param.debug_inputs`
old = "        vars = self.get_input_elements() if not self._param.debug_inputs else self._param.debug_inputs\n"
new = (
    "        vars = self.get_input_elements() if not self._param.debug_inputs else self._param.debug_inputs\n"
    "        import sys\n"
    "        print(f'[DBG-LLM] _prepare_prompt_variables vars keys={list(vars.keys())}', flush=True)\n"
    "        for _k, _o in vars.items():\n"
    "            _v = _o.get('value') if isinstance(_o, dict) else _o\n"
    "            print(f'[DBG-LLM]   var {_k!r} value_len={len(str(_v)) if _v is not None else 0} head={str(_v)[:200]!r}', flush=True)\n"
)
if old not in src:
    print("ERROR: marker line 1 not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)

# Insert debug right before _generate_async return — capture final msg
old2 = "    async def _generate_async(self, msg: list[dict], **kwargs) -> str:\n"
new2 = (
    "    async def _generate_async(self, msg: list[dict], **kwargs) -> str:\n"
    "        import sys\n"
    "        print(f'[DBG-LLM] _generate_async num_msgs={len(msg)}', flush=True)\n"
    "        for _i, _m in enumerate(msg):\n"
    "            _c = _m.get('content','')\n"
    "            print(f'[DBG-LLM]   msg[{_i}] role={_m.get(\"role\")} content_len={len(_c)} head={_c[:200]!r}', flush=True)\n"
)
if old2 not in src:
    print("ERROR: marker line 2 not found")
    raise SystemExit(1)
src = src.replace(old2, new2, 1)

with open('/ragflow/agent/component/llm.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("patched OK")
