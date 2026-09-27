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

import pytest

from common.text_utils import (
    contains_hebrew,
    hebrew_variants,
    looks_visual_order,
    reorder_bidi,
    reorder_bidi_sections,
)


HEBREW_LOGICAL = "שלום עולם"
ENGLISH_ONLY = "Hello world"
MIXED = "Hello שלום 123"
HEBREW_SENTENCE = "הפיקוח על הבנקים מפרסם הנחיות לכל הבנקים בישראל"
# The same sentence as a PDF extractor emits it: characters in x-coordinate order.
HEBREW_SENTENCE_VISUAL = "לארשיב םיקנבה לכל תויחנה םסרפמ םיקנבה לע חוקיפה"


class TestReorderBidiSections:
    """reorder_bidi_sections is the entrypoint that naive.py calls for
    non-PDF parser branches. The PDF branch must NEVER call this — pdf_parser
    already reorders at extraction time, so a second pass would round-trip
    text back to visual order. These tests pin down both sides of that
    contract."""

    def test_disabled_is_passthrough(self):
        """When the flag is False, sections are returned untouched.
        This is the safety guarantee that lets us land the wiring without
        touching existing non-Hebrew workloads."""
        sections = [(HEBREW_LOGICAL, "")]
        result = reorder_bidi_sections(sections, enabled=False)
        assert result is sections  # Same object, no copy, no mutation.

    def test_empty_sections_passthrough(self):
        assert reorder_bidi_sections([], enabled=True) == []
        assert reorder_bidi_sections(None, enabled=True) is None

    def test_english_only_unchanged_when_enabled(self):
        """contains_hebrew short-circuits inside reorder_bidi, so pure
        English text is a no-op even with the flag on."""
        sections = [(ENGLISH_ONLY, "")]
        result = reorder_bidi_sections(sections, enabled=True)
        assert result[0][0] == ENGLISH_ONLY

    def test_logical_hebrew_is_not_flipped(self):
        """DOCX/XLSX/HTML/MD already store Hebrew in logical order. With
        lang=="Hebrew" naive.py enables this helper for all of them, so it
        must leave correct text alone — reorder_bidi is not idempotent and
        an unconditional call reverses every word."""
        sections = [(HEBREW_SENTENCE, "")]
        result = reorder_bidi_sections(sections, enabled=True)
        assert result[0][0] == HEBREW_SENTENCE

    def test_visual_hebrew_is_reordered(self):
        """Text that really arrived reversed (e.g. force_bidi_reorder on a
        legacy export) is still repaired."""
        sections = [(HEBREW_SENTENCE_VISUAL, "")]
        result = reorder_bidi_sections(sections, enabled=True)
        assert result[0][0] == HEBREW_SENTENCE

    def test_running_twice_is_stable(self):
        once = reorder_bidi_sections([(HEBREW_SENTENCE_VISUAL, "")], enabled=True)
        twice = reorder_bidi_sections(once, enabled=True)
        assert twice[0][0] == once[0][0] == HEBREW_SENTENCE

    def test_tuple_shape_preserved(self):
        """DOCX sections are tuples of (text, image, ...). The trailing
        elements (images, table refs) must survive untouched."""
        sentinel = object()
        sections = [(HEBREW_LOGICAL, "img-blob", sentinel)]
        result = reorder_bidi_sections(sections, enabled=True)
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 3
        assert result[0][1] == "img-blob"
        assert result[0][2] is sentinel

    def test_list_shape_preserved(self):
        sentinel = object()
        sections = [[HEBREW_LOGICAL, "img-blob", sentinel]]
        result = reorder_bidi_sections(sections, enabled=True)
        assert isinstance(result[0], list)
        assert result[0][1] == "img-blob"
        assert result[0][2] is sentinel

    def test_bare_string_section(self):
        """Some parser branches in naive.py wrap text into tuples before
        calling _normalize, but the helper accepts bare strings too for
        defensive symmetry with the existing _normalize_section_text helper."""
        sections = [HEBREW_LOGICAL, ENGLISH_ONLY]
        result = reorder_bidi_sections(sections, enabled=True)
        assert isinstance(result[0], str)
        assert result[1] == ENGLISH_ONLY  # Pure English untouched.

    def test_empty_tuple_in_list(self):
        """Defensive: an empty tuple inside the section list should not
        crash. naive.py occasionally produces these."""
        result = reorder_bidi_sections([()], enabled=True)
        assert result == [()]

    def test_mixed_content_tuple(self):
        """Mixed Hebrew + Latin should still be processed; bidi handles the
        directional runs."""
        sections = [(MIXED, "")]
        result = reorder_bidi_sections(sections, enabled=True)
        assert "Hello" in result[0][0]  # Latin run preserved.
        assert contains_hebrew(result[0][0])

    def test_multiple_sections(self):
        sections = [
            (HEBREW_LOGICAL, ""),
            (ENGLISH_ONLY, ""),
            (MIXED, ""),
        ]
        result = reorder_bidi_sections(sections, enabled=True)
        assert len(result) == 3
        assert result[1][0] == ENGLISH_ONLY  # Pure English: byte-identical.


class TestContainsHebrew:
    """Pin down behavior that reorder_bidi relies on for its fast path."""

    def test_pure_english(self):
        assert contains_hebrew("Hello world") is False

    def test_pure_hebrew(self):
        assert contains_hebrew("שלום") is True

    def test_mixed(self):
        assert contains_hebrew("hello שלום") is True

    def test_empty(self):
        assert contains_hebrew("") is False
        assert contains_hebrew(None) is False

    def test_non_string(self):
        assert contains_hebrew(123) is False
        assert contains_hebrew([]) is False

    def test_hebrew_presentation_forms(self):
        # U+FB1D..U+FB4F range, used by some legacy PDF encoders.
        assert contains_hebrew("שׁ") is True


class TestLooksVisualOrder:
    """The gate reorder_bidi_sections relies on to avoid flipping correct text."""

    def test_logical_sentence(self):
        assert looks_visual_order(HEBREW_SENTENCE) is False

    def test_visual_sentence(self):
        assert looks_visual_order(HEBREW_SENTENCE_VISUAL) is True

    def test_too_little_evidence_is_left_alone(self):
        assert looks_visual_order("םולש") is False
        assert looks_visual_order("Hello world") is False
        assert looks_visual_order(None) is False


class TestReorderBidiPassthrough:
    """The fast paths inside reorder_bidi matter for the PDF safety story:
    if reorder_bidi is ever accidentally called on non-Hebrew text from the
    PDF branch, it must not mangle the input."""

    def test_english_unchanged(self):
        assert reorder_bidi("Hello world") == "Hello world"

    def test_none_unchanged(self):
        assert reorder_bidi(None) is None

    def test_empty_unchanged(self):
        assert reorder_bidi("") == ""

    def test_non_string_unchanged(self):
        assert reorder_bidi(123) == 123


class TestHebrewVariants:
    def test_strips_definite_article(self):
        v = dict(hebrew_variants("הנרכש"))
        assert v["נרכש"] == 0.6

    def test_strips_prefix_chain(self):
        v = dict(hebrew_variants("ובהסכם"))
        # ו -> "בהסכם", ו+ב -> "הסכם"; a chain of two article letters ("ובה")
        # is not a Hebrew proclitic, so "סכם" must not appear
        assert "בהסכם" in v and "הסכם" in v
        assert "סכם" not in v

    def test_adds_prefixes_to_stem_not_to_prefixed_word(self):
        words = [w for w, _ in hebrew_variants("המטבע")]
        assert "מטבע" in words
        assert "במטבע" in words
        assert "ההמטבע" not in words

    def test_bare_word_gets_prefixed_forms(self):
        v = dict(hebrew_variants("נרכש"))
        assert v["הנרכש"] == 0.4

    @pytest.mark.parametrize("word", ["בנק", "הון", "ללא"])
    def test_short_stems_are_not_cut(self, word):
        assert all(len(w) >= 3 for w, _ in hebrew_variants(word))
        assert word[1:] not in dict(hebrew_variants(word))

    @pytest.mark.parametrize("token", ["xx", "882", "1,500", "מט\"ח", "", "a"])
    def test_non_hebrew_or_punctuated_untouched(self, token):
        assert hebrew_variants(token) == []

    def test_capped(self):
        assert len(hebrew_variants("וכשהבנקים")) <= 5
