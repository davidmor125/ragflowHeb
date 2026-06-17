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
"""Unit tests for the glossary CSV parser.

Only parse_csv is exercised here (pure function, no DB). DB-touching paths
(upsert_many, list_for_kb) need a live DB and belong in integration tests."""

import pytest

from api.db.services.glossary_term_service import (
    GlossaryParseError,
    parse_csv,
    _parse_aliases,
)


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------

class TestParseCsvHappyPath:

    def test_simple_three_column(self):
        csv_bytes = (
            "term,full_form,definition\n"
            "DPA,Deposit Account,A bank deposit account\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["term"] == "DPA"
        assert rows[0]["full_form"] == "Deposit Account"
        assert rows[0]["definition"] == "A bank deposit account"
        assert rows[0]["aliases"] == []

    def test_with_aliases(self):
        csv_bytes = (
            "term,full_form,definition,aliases\n"
            "DPA,Deposit Account,A bank deposit,DA;Deposit\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["aliases"] == ["DA", "Deposit"]

    def test_hebrew_terms(self):
        csv_bytes = (
            "term,full_form,definition,aliases\n"
            'דנ"פ,דמי ניהול פקדון,עמלה עבור אחזקה,דנפ;ד.נ.פ\n'
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["term"] == 'דנ"פ'
        assert rows[0]["full_form"] == "דמי ניהול פקדון"
        assert rows[0]["aliases"] == ["דנפ", "ד.נ.פ"]


# ---------------------------------------------------------------------------
# Encoding edge cases — these are why we exist
# ---------------------------------------------------------------------------

class TestParseCsvEncoding:

    def test_utf8_bom_stripped_from_first_header(self):
        """Excel-on-Windows saves CSV as UTF-8-with-BOM. Without BOM
        handling the first column name becomes '﻿termv', breaking
        the required-headers check."""
        bom = "﻿"
        csv_bytes = (
            bom + "term,full_form,definition\n"
            "X,X full,X def\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert len(rows) == 1
        assert rows[0]["term"] == "X"

    def test_invalid_utf8_rejected(self):
        # Latin-1 byte sequence that is not valid UTF-8.
        csv_bytes = b"term,full_form,definition\n\xfftest,full,def\n"
        with pytest.raises(GlossaryParseError, match="UTF-8"):
            parse_csv(csv_bytes)

    def test_quoted_values_with_embedded_commas(self):
        csv_bytes = (
            'term,full_form,definition\n'
            '"D,P,A","Deposit, Payment, Account","Has, commas"\n'
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["term"] == "D,P,A"
        assert rows[0]["full_form"] == "Deposit, Payment, Account"

    def test_escaped_double_quotes(self):
        # CSV escaping: "" inside quoted field == literal "
        csv_bytes = (
            'term,full_form,definition\n'
            '"דנ""פ","שם מלא","הגדרה"\n'
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["term"] == 'דנ"פ'


# ---------------------------------------------------------------------------
# Validation failures — must point at the right line for the UI
# ---------------------------------------------------------------------------

class TestParseCsvValidation:

    def test_empty_csv(self):
        with pytest.raises(GlossaryParseError, match="empty"):
            parse_csv(b"")

    def test_missing_required_header(self):
        csv_bytes = b"term,definition\nX,X def\n"
        with pytest.raises(GlossaryParseError, match="full_form"):
            parse_csv(csv_bytes)

    def test_empty_term_row(self):
        csv_bytes = (
            "term,full_form,definition\n"
            ",full,def\n"
        ).encode("utf-8")
        with pytest.raises(GlossaryParseError) as exc:
            parse_csv(csv_bytes)
        # Header is line 1, this row is line 2.
        assert exc.value.row == 2

    def test_empty_definition_row(self):
        csv_bytes = (
            "term,full_form,definition\n"
            "Good,Good full,Good def\n"
            "Bad,Bad full,\n"
        ).encode("utf-8")
        with pytest.raises(GlossaryParseError) as exc:
            parse_csv(csv_bytes)
        assert exc.value.row == 3
        assert "definition" in str(exc.value)

    def test_duplicate_term_in_csv(self):
        csv_bytes = (
            "term,full_form,definition\n"
            "X,first,first def\n"
            "X,second,second def\n"
        ).encode("utf-8")
        with pytest.raises(GlossaryParseError, match="duplicate"):
            parse_csv(csv_bytes)

    def test_blank_lines_skipped_silently(self):
        """Excel often appends blank trailing rows. Don't punish the user."""
        csv_bytes = (
            "term,full_form,definition\n"
            "X,X full,X def\n"
            "\n"
            ",,\n"
            "Y,Y full,Y def\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert len(rows) == 2
        assert rows[0]["term"] == "X"
        assert rows[1]["term"] == "Y"

    def test_term_too_long(self):
        long_term = "x" * 200
        csv_bytes = (
            f"term,full_form,definition\n{long_term},full,def\n"
        ).encode("utf-8")
        with pytest.raises(GlossaryParseError, match="term too long"):
            parse_csv(csv_bytes)

    def test_header_with_whitespace_normalized(self):
        csv_bytes = (
            " Term , Full_Form , Definition \n"
            "X,X full,X def\n"
        ).encode("utf-8")
        rows = parse_csv(csv_bytes)
        assert rows[0]["term"] == "X"


# ---------------------------------------------------------------------------
# Aliases parsing
# ---------------------------------------------------------------------------

class TestParseAliases:

    def test_empty(self):
        assert _parse_aliases("") == []

    def test_single(self):
        assert _parse_aliases("foo") == ["foo"]

    def test_semicolon_separated(self):
        assert _parse_aliases("foo;bar;baz") == ["foo", "bar", "baz"]

    def test_dedupe_preserves_order(self):
        assert _parse_aliases("foo;bar;foo") == ["foo", "bar"]

    def test_strip_whitespace(self):
        assert _parse_aliases("  foo  ;  bar  ") == ["foo", "bar"]

    def test_skip_empties(self):
        assert _parse_aliases("foo;;bar;") == ["foo", "bar"]

    def test_hebrew(self):
        assert _parse_aliases("דנפ;ד.נ.פ") == ["דנפ", "ד.נ.פ"]
