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

"""Diagnose Hebrew PDF extraction in RAGFlow's deepdoc pipeline.

Run this from the project root:

    python tools/scripts/diagnose_hebrew_pdf.py /path/to/hebrew.pdf

What it does (no API keys, no network, no DB):
  1. Open the PDF with both PlainParser (pypdf-based) and pdfplumber.
  2. Print the first N lines from each, marking Hebrew runs.
  3. Re-run the lines through the same bidi helper RAGFlow uses, and
     diff the result so you can see whether reordering changed anything.
  4. Report whether python-bidi is installed and whether Hebrew niqqud is
     present in the file.

Use this BEFORE running the full chunking pipeline to confirm the basic
extraction step recovers logical-order Hebrew. If the diff is empty, your
PDF is already in logical order and no bidi work is needed for that file.
"""

from __future__ import annotations

import argparse
import os
import sys
from io import BytesIO


def _add_project_root_to_path() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)


_add_project_root_to_path()

# These imports rely on the project root being on sys.path.
from common.text_utils import (  # noqa: E402
    HEBREW_NIQQUD_RE,
    HEBREW_RE,
    contains_hebrew,
    reorder_bidi,
)


def _has_bidi_module() -> bool:
    try:
        import bidi.algorithm  # noqa: F401
        return True
    except ImportError:
        return False


def _highlight_hebrew(line: str) -> str:
    """Wrap Hebrew runs in <<...>> for terminal visibility."""
    out: list[str] = []
    in_run = False
    for ch in line:
        if HEBREW_RE.match(ch):
            if not in_run:
                out.append("<<")
                in_run = True
            out.append(ch)
        else:
            if in_run:
                out.append(">>")
                in_run = False
            out.append(ch)
    if in_run:
        out.append(">>")
    return "".join(out)


def _read_lines_pypdf(path: str, max_pages: int) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    lines: list[str] = []
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            if line.strip():
                lines.append(line)
    return lines


def _read_lines_pdfplumber(path: str, max_pages: int) -> list[str]:
    try:
        import pdfplumber
    except ImportError:
        return []
    lines: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if line.strip():
                    lines.append(line)
    return lines


def _summary_stats(lines: list[str]) -> dict:
    total_chars = sum(len(line) for line in lines)
    hebrew_chars = sum(1 for line in lines for ch in line if HEBREW_RE.match(ch))
    niqqud_chars = sum(1 for line in lines for ch in line if HEBREW_NIQQUD_RE.match(ch))
    hebrew_lines = sum(1 for line in lines if contains_hebrew(line))
    return {
        "total_lines": len(lines),
        "hebrew_lines": hebrew_lines,
        "total_chars": total_chars,
        "hebrew_chars": hebrew_chars,
        "niqqud_chars": niqqud_chars,
    }


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _print_lines(lines: list[str], max_lines: int) -> None:
    for i, line in enumerate(lines[:max_lines], 1):
        marker = "H" if contains_hebrew(line) else " "
        print(f"  [{i:03d}{marker}] {_highlight_hebrew(line)}")
    if len(lines) > max_lines:
        print(f"  ... ({len(lines) - max_lines} more lines suppressed)")


def _print_bidi_diff(lines: list[str], max_lines: int) -> None:
    changed = 0
    shown = 0
    for line in lines:
        if not contains_hebrew(line):
            continue
        reordered = reorder_bidi(line)
        if reordered != line:
            changed += 1
            if shown < max_lines:
                print(f"  RAW : {_highlight_hebrew(line)}")
                print(f"  BIDI: {_highlight_hebrew(reordered)}")
                print()
                shown += 1
    print(f"  bidi reorder changed {changed} of {sum(1 for l in lines if contains_hebrew(l))} Hebrew lines")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", help="Path to a Hebrew PDF to inspect")
    parser.add_argument("--max-pages", type=int, default=3, help="How many pages to read (default: 3)")
    parser.add_argument("--max-lines", type=int, default=20, help="How many lines to print per section (default: 20)")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"ERROR: file not found: {args.pdf}", file=sys.stderr)
        return 2

    _print_section("Environment")
    print(f"  PDF: {args.pdf}")
    print(f"  python-bidi installed: {_has_bidi_module()}")
    if not _has_bidi_module():
        print("  WARNING: install python-bidi to enable RTL reordering: pip install python-bidi")

    # Path 1: pypdf (matches PlainParser at deepdoc/parser/pdf_parser.py).
    _print_section(f"pypdf extraction (first {args.max_pages} pages)")
    try:
        pypdf_lines = _read_lines_pypdf(args.pdf, args.max_pages)
    except Exception as exc:
        print(f"  pypdf failed: {exc}")
        pypdf_lines = []
    _print_lines(pypdf_lines, args.max_lines)
    print()
    print("  stats:", _summary_stats(pypdf_lines))

    # Path 2: pdfplumber (matches the per-character path in RAGFlowPdfParser).
    _print_section(f"pdfplumber extraction (first {args.max_pages} pages)")
    plumber_lines = _read_lines_pdfplumber(args.pdf, args.max_pages)
    if not plumber_lines:
        print("  pdfplumber unavailable or returned no text")
    else:
        _print_lines(plumber_lines, args.max_lines)
        print()
        print("  stats:", _summary_stats(plumber_lines))

    # Bidi diff: shows what RAGFlow's reorder_bidi would do to the lines.
    _print_section(f"Bidi reorder diff (pypdf, first {args.max_lines} changed lines)")
    if pypdf_lines:
        _print_bidi_diff(pypdf_lines, args.max_lines)

    _print_section("How to read this report")
    print("  - <<...>> brackets surround Hebrew runs.")
    print("  - 'H' marker on a line means contains_hebrew() returned True.")
    print("  - In the bidi diff section, RAW is what the extractor returned and")
    print("    BIDI is what RAGFlow stores after reordering. If RAW already reads")
    print("    naturally right-to-left, no further work is needed for this file.")
    print("  - niqqud_chars > 0 means the PDF uses Hebrew vowel points; the")
    print("    embedding model may or may not handle them — strip with")
    print("    common.text_utils.strip_niqqud() if retrieval quality is poor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
