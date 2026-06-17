"""Inject correct logging into dialog_service.py to capture the actual prompt."""
import re
path = "/ragflow/api/db/services/dialog_service.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Remove any prior bad injection
text = re.sub(
    r"\nimport logging as _audit_log.*?=== AUDIT_PROMPT_END.*?\)\)\n",
    "\n",
    text, flags=re.DOTALL,
)

# Find anchor and inject correctly indented block
anchor = '    msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs)+attachments_}]\n'
inject = (
    '    msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs)+attachments_}]\n'
    '    import logging as _audit_log\n'
    '    _audit_content = msg[0]["content"]\n'
    '    _audit_log.warning("=== AUDIT_PROMPT_START ===\\n%s\\n=== AUDIT_PROMPT_END (len=%d chars) ===", _audit_content, len(_audit_content))\n'
)
if anchor in text:
    text = text.replace(anchor, inject, 1)
    print("INJECTED")
else:
    print("ANCHOR NOT FOUND - file may already be patched or layout changed")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
