"""Manually run the RAGFlow naive chunker on 34320.html with chunk_token_num=256
and see which chunk is too big."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from deepdoc.parser import HtmlParser

raw = Path(r"C:/develop/html_output/_eval_report/newtest/טסט/34320.html").read_bytes()
sections = HtmlParser()(str(Path(r"C:/develop/html_output/_eval_report/newtest/טסט/34320.html")), binary=raw, chunk_token_num=256)

print(f"sections: {len(sections)}")
for i, s in enumerate(sections):
    s_str = s if isinstance(s, str) else (s[0] if s else "")
    n_chars = len(s_str)
    # Crude token count: ~4 chars per token in mixed text. Real tokenizer ratios vary.
    crude_tokens = n_chars // 3  # Hebrew is denser per token
    marker = " <-- BIG!" if crude_tokens > 4000 else ""
    print(f"  [{i}] chars={n_chars:>6}  ~tokens={crude_tokens:>5}{marker}")
    if crude_tokens > 4000:
        print(f"      first 300: {s_str[:300]!r}")
        print(f"      last 300:  {s_str[-300:]!r}")
