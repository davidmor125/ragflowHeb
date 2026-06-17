#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

from __future__ import annotations

import logging
import re
import unicodedata


ARABIC_PRESENTATION_FORMS_RE = re.compile(r"[ﭐ-﷿ﹰ-﻿]")

# Hebrew block (U+0590..U+05FF) covers letters, niqqud and cantillation.
# Hebrew presentation forms live at U+FB1D..U+FB4F.
HEBREW_RE = re.compile(r"[֐-׿יִ-ﭏ]")
HEBREW_NIQQUD_RE = re.compile(r"[֑-ׇ]")


def normalize_arabic_digits(text: str | None) -> str | None:
    if text is None or not isinstance(text, str):
        return text

    out = []
    for ch in text:
        code = ord(ch)
        if 0x0660 <= code <= 0x0669:
            out.append(chr(code - 0x0660 + 0x30))
        elif 0x06F0 <= code <= 0x06F9:
            out.append(chr(code - 0x06F0 + 0x30))
        else:
            out.append(ch)
    return "".join(out)


def normalize_arabic_presentation_forms(text: str | None) -> str | None:
    """Normalize Arabic presentation forms to canonical text when present."""
    if text is None or not isinstance(text, str):
        return text
    if not ARABIC_PRESENTATION_FORMS_RE.search(text):
        return text
    return unicodedata.normalize("NFKC", text)


def contains_hebrew(text: str | None) -> bool:
    if not text or not isinstance(text, str):
        return False
    return bool(HEBREW_RE.search(text))


def is_hebrew(text: str | None, threshold: float = 0.2) -> bool:
    """True when at least `threshold` of non-space characters are Hebrew.

    Threshold defaults to 0.2 (matches the existing is_chinese() heuristic in
    rag/nlp/__init__.py:256). Whitespace and ASCII digits/punctuation do not
    count toward the denominator, so short Hebrew snippets surrounded by
    numbers still classify as Hebrew.
    """
    if not text or not isinstance(text, str):
        return False
    significant = [c for c in text if not c.isspace() and not c.isascii()]
    if not significant:
        # Pure ASCII or whitespace; only Hebrew if HEBREW_RE matched anything.
        return bool(HEBREW_RE.search(text))
    hebrew_count = sum(1 for c in significant if HEBREW_RE.match(c))
    return hebrew_count / len(significant) >= threshold


def strip_niqqud(text: str | None) -> str | None:
    """Remove Hebrew niqqud (vowel points) and cantillation marks.

    Useful before tokenization, since most embedding/tokenizer models are
    trained on niqqud-free Hebrew. Leaves base letters and final forms intact.
    """
    if text is None or not isinstance(text, str):
        return text
    if not HEBREW_NIQQUD_RE.search(text):
        return text
    return HEBREW_NIQQUD_RE.sub("", text)


_BIDI_IMPORT_FAILED = False


def reorder_bidi(text: str | None, base_dir: str = "R") -> str | None:
    """Apply the Unicode Bidirectional Algorithm to reorder visual-order text
    into logical order.

    PDF text extractors (pdfplumber, pypdf) often return RTL runs in visual
    order — i.e., the first character of an Arabic/Hebrew word ends up last in
    the string. python-bidi's ``get_display`` is the inverse operation: it
    *generates* visual order from logical order. To recover logical order from
    visual order we apply ``get_display`` and assume the result was symmetric;
    in practice this round-trips correctly for the typical PDF case where the
    extractor laid characters left-to-right by x-coordinate. base_dir="R" sets
    the paragraph base direction to RTL.

    Returns the input untouched when:
      * input is None / not a str
      * no Hebrew / RTL characters are present (cheap fast path)
      * python-bidi is not installed (logged once)
    """
    global _BIDI_IMPORT_FAILED
    if text is None or not isinstance(text, str):
        return text
    if not contains_hebrew(text):
        return text
    if _BIDI_IMPORT_FAILED:
        return text
    try:
        from bidi.algorithm import get_display
    except ImportError:
        _BIDI_IMPORT_FAILED = True
        logging.warning(
            "python-bidi is not installed; Hebrew/RTL text will not be "
            "reordered. Install with: pip install python-bidi"
        )
        return text
    try:
        return get_display(text, base_dir=base_dir)
    except Exception:
        logging.exception("bidi reorder failed; returning original text")
        return text


def reorder_bidi_sections(sections, enabled: bool):
    """Apply reorder_bidi to a sections list as produced by non-PDF parsers.

    Sections may be a list of:
      * tuple (text, image, ...) — DOCX/MD shape
      * list  [text, image, ...] — same shape, mutable variant
      * str                      — bare text (some branches in naive.py)

    Pure passthrough when ``enabled`` is False so callers can wire this in
    unconditionally without risk to non-Hebrew workloads. ``contains_hebrew``
    inside ``reorder_bidi`` short-circuits per-string when no Hebrew is
    present, so the cost on mixed corpora is a single regex search per item.

    IMPORTANT: do NOT call this from the PDF branch — pdf_parser.py already
    applies reorder_bidi at extraction time (box level + plaintext level), so
    a second pass here would round-trip back to visual order.
    """
    if not enabled or not sections:
        return sections

    out = []
    for section in sections:
        if isinstance(section, tuple):
            if not section:
                out.append(section)
                continue
            out.append((reorder_bidi(section[0]), *section[1:]))
        elif isinstance(section, list):
            if not section:
                out.append(section)
                continue
            out.append([reorder_bidi(section[0]), *section[1:]])
        else:
            out.append(reorder_bidi(section))
    return out
