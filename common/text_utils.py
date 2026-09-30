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


_HEBREW_FINAL_LETTERS = frozenset("ךםןףץ")
_HEBREW_WORD_RE = re.compile(r"[֐-׿]{2,}")

_HEBREW_LETTERS_ONLY_RE = re.compile(r"^[א-ת]+$")
# Proclitic chains Hebrew glues to the front of a word: optional ו, then an
# optional ש/כש/מש/לכש, then an optional ה/ב/כ/ל/מ ("ו"+"כש"+"ה" = "וכשה").
_HEBREW_PREFIXES = sorted(
    {v + s + p for v in ("", "ו") for s in ("", "ש", "כש", "מש", "לכש") for p in ("", "ה", "ב", "כ", "ל", "מ")} - {""},
    key=len,
)
_HEBREW_ADDED_PREFIXES = ("ה", "ב", "ל", "ו", "מ", "ש")


def hebrew_variants(token: str, min_stem: int = 3, max_variants: int = 5) -> list[tuple[str, float]]:
    """Prefix variants of one Hebrew word for full-text query expansion.

    The index is whitespace-tokenized with no Hebrew morphology, and full-text
    match gates vector search too, so a query word "הנרכש" never reached a
    chunk that says "מטבע נרכש". Returns ``[(variant, weight), ...]`` without
    the token itself:

    * stripped forms (weight 0.6): each proclitic split that leaves at least
      ``min_stem`` letters, so "בנק", "הון", "ללא" are never cut down;
    * added forms (weight 0.4): the bare word with a common prefix, for the
      reverse case (query "נרכש", document "הנרכש").

    Only letters-only Hebrew tokens are expanded; anything with digits, Latin
    or punctuation is returned unchanged (empty list). Wrong splits such as
    "מסמך" -> "סמך" are possible, which is why variants weigh less than the
    original and are capped.
    """
    if not token or not _HEBREW_LETTERS_ONLY_RE.match(token):
        return []
    out: list[tuple[str, float]] = []
    seen = {token}
    for p in _HEBREW_PREFIXES:
        if token.startswith(p) and len(token) - len(p) >= min_stem:
            v = token[len(p):]
            if v not in seen:
                seen.add(v)
                out.append((v, 0.6))
    # Add prefixes to the stem, not to an already-prefixed word: "המטבע" should
    # yield "במטבע"/"למטבע", not "ההמטבע".
    stem = out[0][0] if out else token
    if len(stem) >= min_stem:
        for p in _HEBREW_ADDED_PREFIXES:
            v = p + stem
            if v not in seen:
                seen.add(v)
                out.append((v, 0.4))
    return out[:max_variants]


def looks_visual_order(text: str | None) -> bool:
    """True when Hebrew words appear to be stored in visual (reversed) order.

    Hebrew final forms (ך ם ן ף ץ) are only legal at the END of a word, so a
    reversed string puts them at the start. Comparing how many words start vs.
    end with a final form separates the two cases without needing to know how
    the text was produced.

    This exists because ``reorder_bidi`` is NOT idempotent — running it on
    already-logical text flips it into visual order. Callers that cannot know
    whether their input was reordered upstream must gate on this first.

    Conservative by design: returns False when there is too little evidence
    (fewer than two multi-letter Hebrew words), so the caller leaves the text
    alone rather than risk corrupting correct text.
    """
    if not text or not isinstance(text, str):
        return False
    words = _HEBREW_WORD_RE.findall(text)
    if len(words) < 2:
        return False
    starts = sum(1 for w in words if w[0] in _HEBREW_FINAL_LETTERS)
    ends = sum(1 for w in words if w[-1] in _HEBREW_FINAL_LETTERS)
    return starts > ends


def reorder_bidi_if_visual(text: str | None) -> str | None:
    """Reorder only when the text actually looks reversed. Safe to call twice."""
    if looks_visual_order(text):
        return reorder_bidi(text)
    return text


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


_BRACKETS_BALANCED_RE = re.compile(r"\([^()\n]{1,60}\)|\[[^\[\]\n]{1,60}\]")
_BRACKETS_FLIPPED_RE = re.compile(r"\)[^()\n]{1,60}\(|\][^\[\]\n]{1,60}\[")
_BRACKET_SWAP = str.maketrans("()[]{}", ")(][}{")


def brackets_look_mirrored(texts) -> bool:
    """True when the Hebrew texts of one document mostly read ")x(" / "]x[".

    Whether reorder_bidi() leaves brackets the right way round depends on the
    PDF producer: Word 2016 and ABBYY FineReader store the mirrored glyph's
    codepoint, so every pair in the document comes out flipped (measured: 7 of
    15 test PDFs, all Bank of Israel circulars), while Skia/Ghostscript/Acrobat
    exports come out right. The orientation is consistent within a document,
    so decide once per document by majority, never per line.
    """
    balanced = flipped = 0
    for t in texts:
        if t and contains_hebrew(t):
            balanced += len(_BRACKETS_BALANCED_RE.findall(t))
            flipped += len(_BRACKETS_FLIPPED_RE.findall(t))
    return flipped >= 3 and flipped > 2 * balanced


def swap_brackets(text: str | None) -> str | None:
    """Swap ( ) [ ] { } -- the fix-up when brackets_look_mirrored() is True."""
    if not text:
        return text
    return text.translate(_BRACKET_SWAP)


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

    Each item goes through ``reorder_bidi_if_visual``, not ``reorder_bidi``:
    DOCX/XLSX/HTML/MD/TXT store Hebrew in logical order already, and an
    unconditional reorder flips it ("הפיקוח על הבנקים" -> "םיקנבה לע חוקיפה").
    Only text that actually looks reversed is touched.
    """
    if not enabled or not sections:
        return sections

    out = []
    for section in sections:
        if isinstance(section, tuple):
            if not section:
                out.append(section)
                continue
            out.append((reorder_bidi_if_visual(section[0]), *section[1:]))
        elif isinstance(section, list):
            if not section:
                out.append(section)
                continue
            out.append([reorder_bidi_if_visual(section[0]), *section[1:]])
        else:
            out.append(reorder_bidi_if_visual(section))
    return out
