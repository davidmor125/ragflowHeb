"""Keep a reasoning model's thinking out of the non-streaming agent answer.

The canvas marks a model's reasoning with message events flagged
start_to_think / end_to_think (the web UI folds it away), but the
non-streaming /api/v1/agents/<id>/completions joined every message event,
so gpt-oss's English reasoning came back glued to the Hebrew answer.
Patched into the image's api/apps/sdk/session.py at build time (the repo copy
differs from v0.25.0's). Idempotent; fails the build if an anchor is missing.

Usage: python patch_agent_think.py <path/to/api/apps/sdk/session.py>
"""
import sys

PATCHES = [
    ('''    full_content = ""
    reference = {}
    final_ans = ""
''', '''    full_content = ""
    reference = {}
    final_ans = ""
    in_think = False  # reasoning between start_to_think/end_to_think is not answer text
'''),
    ('''            if ans["event"] == "message":
                full_content += ans["data"]["content"]
''', '''            if ans["event"] == "message":
                if ans["data"].get("start_to_think"):
                    in_think = True
                elif ans["data"].get("end_to_think"):
                    in_think = False
                elif not in_think:
                    full_content += ans["data"]["content"]
'''),
]

path = sys.argv[1]
src = open(path, encoding="utf-8").read()
crlf = "\r\n" in src
text = src.replace("\r\n", "\n")
if "in_think = False  # reasoning between" in text:
    print(f"{path}: already patched")
    sys.exit(0)
for old, new in PATCHES:
    n = text.count(old)
    if n != 1:
        sys.exit(f"{path}: anchor found {n} times, expected 1; not patching")
    text = text.replace(old, new)
open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print(f"{path}: patched")
