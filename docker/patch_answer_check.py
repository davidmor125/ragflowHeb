"""Insert the answer grounding check (rag/answer_check.py) into
dialog_service.decorate_answer. Run at image build time by Dockerfile.patched:
the released v0.25.0 dialog_service differs from this repo's copy (glossary,
Langfuse API), so the hook is patched in rather than copying the file.
Idempotent; fails the build if the anchor is not found exactly once.

Usage: python patch_answer_check.py <path/to/dialog_service.py>
"""
import sys

ANCHOR = '''            refs = deepcopy(kbinfos)
            for c in refs["chunks"]:
                if c.get("vector"):
                    del c["vector"]
'''
MARKER = "rag.answer_check"
HOOK = '''            # Grounding check (rag/answer_check.py): numbers in the answer must
            # appear in the retrieved chunks, and the answer should cite one.
            try:
                from rag.answer_check import ANSWER_CHECK_MODE, check_answer, warning_line
                if ANSWER_CHECK_MODE != "off":
                    _verification = check_answer(answer, kbinfos.get("chunks", []), " ".join(questions))
                    refs["verification"] = _verification
                    if ANSWER_CHECK_MODE == "warn":
                        answer += warning_line(_verification)
            except Exception:
                logging.exception("answer check failed; answer returned unchecked")
'''

path = sys.argv[1]
src = open(path, encoding="utf-8").read()
crlf = "\r\n" in src
text = src.replace("\r\n", "\n")
if MARKER in text:
    print(f"{path}: already patched")
    sys.exit(0)
n = text.count(ANCHOR)
if n != 1:
    sys.exit(f"{path}: anchor found {n} times, expected 1; not patching")
text = text.replace(ANCHOR, ANCHOR + HOOK)
open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print(f"{path}: patched")
