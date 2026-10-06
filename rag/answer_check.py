#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Grounding check of a generated answer against the chunks it was given.

Nothing in the chat path verified an answer: citations are attached by
similarity, so an answer that says "15 ₪" where the procedure says "12 ₪"
is cited exactly like a correct one. Two cheap, model-free checks:

1. Numbers: every amount, rate, date or code in the answer must appear in the
   retrieved chunks (or in the question itself). A number found nowhere is
   either invented or copied from the wrong place.
2. Citations: an answer that uses the knowledge base should cite at least one
   chunk.

RAG_ANSWER_CHECK selects what happens:
  off  - nothing
  flag - (default) the result is attached as reference["verification"]
  warn - flag, and a short Hebrew warning line is appended to the answer
"""
import os
import re

ANSWER_CHECK_MODE = os.environ.get("RAG_ANSWER_CHECK", "flag").strip().lower()

_CITATION_RE = re.compile(r"\[(?:ID:)?\s*(\d+)\]")
_TAG_RE = re.compile(r"<[^>]*>")
_FILE_NAME_RE = re.compile(r"[\w.\-]+\.(?:html?|docx?|pdf|xlsx?|csv|md|txt|json)\b", re.IGNORECASE)
# Amounts, rates, dates, codes: "150,000", "3.2%", "01/01/2026", "090-2012-006", "1.40".
_NUMBER_RE = re.compile(r"\d(?:[\d,./:\-]*\d)?")
# "There is no information" in its usual phrasings; such an answer cites
# nothing by design and must not be flagged for it.
_NO_INFO_RE = re.compile(
    r"(?:ה?מידע|פרטים)\s+(?:אינו|אינם|לא)\s+(?:קיים|קיימים|מופיע|מופיעים|נמצא|נמצאים)"
    r"|(?:אינם|לא)\s+(?:מכיל|מכילים|כוללים|מזכירים|מתייחסים)"
    r"|אין\s+(?:בהם|בנהלים|במסמכים|בקטעים)\s+(?:אזכור|מידע|פרטים)")


def _canon(num):
    """Thousands separators and spacing do not change a number."""
    return num.replace(",", "")


def _digits_text(text):
    """Chunk text with markup removed and separators between digits dropped,
    so "150,000", "150000" and an old-index "1 5 0,000" all compare equal."""
    text = _TAG_RE.sub(" ", text or "").replace("&nbsp;", " ")
    return re.sub(r"(?<=\d)[\s,](?=\d)", "", text)


def _numbers(text):
    out = []
    for m in _NUMBER_RE.findall(text or ""):
        m = m.strip(".,:-/")
        # Lone single digits are mostly list markers ("1.", "2)") and appear
        # everywhere; they would make the check meaningless either way.
        if not m or (len(m) == 1 and m.isdigit()):
            continue
        out.append(m)
    return out


def _contains(haystack, num):
    c = re.escape(_canon(num))
    return re.search(rf"(?<![\d]){c}(?![\d])", haystack) is not None


def check_answer(answer, chunks, question=""):
    """Return a dict: status ("ok" | "warn" | "no_answer"), the numbers that
    are not supported by any chunk, and how many chunks the answer cites."""
    body = _CITATION_RE.sub(" ", answer or "")
    # The answer names its source file ("19868.html"); a file name is not a
    # fact to verify.
    body = _FILE_NAME_RE.sub(" ", body)
    cited = sorted({int(i) for i in _CITATION_RE.findall(answer or "")})
    if _NO_INFO_RE.search(body) and len(body) < 300:
        return {"status": "no_answer", "unsupported_numbers": [], "numbers_checked": 0, "cited_chunks": len(cited)}

    corpus = _digits_text("\n".join((c.get("content_with_weight") or c.get("content") or "") for c in chunks or []))
    asked = _digits_text(question)
    nums = list(dict.fromkeys(_numbers(body)))
    unsupported = [n for n in nums if not _contains(corpus, n) and not _contains(asked, n)]

    reasons = []
    if unsupported:
        reasons.append("unsupported_numbers")
    if chunks and not cited:
        reasons.append("no_citation")
    return {
        "status": "warn" if reasons else "ok",
        "reasons": reasons,
        "unsupported_numbers": unsupported,
        "numbers_checked": len(nums),
        "cited_chunks": len(cited),
    }


def warning_line(result):
    """Hebrew warning appended to the answer in "warn" mode, or ""."""
    if result.get("status") != "warn":
        return ""
    parts = []
    if result.get("unsupported_numbers"):
        parts.append("הערכים " + ", ".join(result["unsupported_numbers"][:5]) + " לא נמצאו בנהלים שאוחזרו")
    if "no_citation" in result.get("reasons", []):
        parts.append("התשובה אינה מצטטת אף נוהל")
    return "\n\n⚠️ בדיקת אמינות: " + "; ".join(parts) + ". יש לאמת מול הנוהל."
