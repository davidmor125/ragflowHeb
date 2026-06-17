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
"""Per-KB banking glossary: storage + CSV bulk import.

CSV format (UTF-8, header row required):
    term,full_form,definition,aliases

- ``term``: surface form that appears in the documents (e.g. דנ"פ). Required.
- ``full_form``: expanded form (e.g. דמי ניהול פקדון). Required.
- ``definition``: one short sentence injected into LLM prompts. Required.
- ``aliases``: optional, semicolon-separated alternate spellings (e.g.
  ``דנפ;ד.נ.פ``). Used to broaden synonym-based query expansion.

Re-uploading a CSV with the same (kb_id, term) updates the existing row;
new terms are inserted; rows already in the DB but absent from the CSV are
left alone (use ``delete_by_id`` for explicit removal). This makes the CSV
an additive bulk-edit tool, not a destructive sync.
"""

import csv
import io
from datetime import datetime

from peewee import IntegrityError

from api.db.db_models import DB, GlossaryTerm
from api.db.services.common_service import CommonService
from common.misc_utils import get_uuid
from common.time_utils import current_timestamp, datetime_format


# Limits picked to keep prompts bounded and the UI responsive. Tune later if
# real-world dictionaries blow past these.
MAX_TERMS_PER_UPLOAD = 5000
MAX_TERM_LEN = 128
MAX_FULL_FORM_LEN = 256
MAX_DEFINITION_LEN = 1000
REQUIRED_HEADERS = ("term", "full_form", "definition")
OPTIONAL_HEADERS = ("aliases",)


class GlossaryParseError(ValueError):
    """Raised when a CSV row fails validation. Carries row number for the UI."""

    def __init__(self, message: str, row: int | None = None):
        super().__init__(message)
        self.row = row


def _strip_bom(text: str) -> str:
    """Excel-on-Windows saves CSV with a UTF-8 BOM. csv.reader does not strip
    it, so the first header column ends up named '﻿termv'. Drop it."""
    return text.lstrip("﻿")


def _parse_aliases(raw: str) -> list[str]:
    """Aliases are semicolon-separated because comma is the CSV delimiter and
    Hebrew terms (e.g. ``בנ"פ``) routinely contain quoted commas."""
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(";")]
    # Dedupe while preserving order; skip empties.
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def parse_csv(content: bytes) -> list[dict]:
    """Decode UTF-8 CSV bytes into validated dict rows.

    Raises ``GlossaryParseError`` on the first invalid row, with .row pointing
    at the 1-based CSV line number (header counts as line 1) so the UI can
    highlight it. Validation is strict on purpose — silently dropping bad rows
    leaves the user with a half-loaded dictionary and no way to know."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise GlossaryParseError(f"file is not valid UTF-8: {e}") from e
    text = _strip_bom(text)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise GlossaryParseError("CSV is empty")
    headers = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise GlossaryParseError(
            f"CSV missing required header columns: {missing}. "
            f"Required: {list(REQUIRED_HEADERS)}, optional: {list(OPTIONAL_HEADERS)}"
        )

    rows: list[dict] = []
    seen_terms: set[str] = set()
    for line_idx, raw_row in enumerate(reader, start=2):  # start=2: line 1 is header
        # Normalize keys: the user's header may have surrounding whitespace.
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        # Skip blank lines silently — Excel often appends them.
        if not any(row.get(h) for h in REQUIRED_HEADERS):
            continue
        term = row.get("term", "")
        full_form = row.get("full_form", "")
        definition = row.get("definition", "")
        if not term:
            raise GlossaryParseError("empty term", row=line_idx)
        if not full_form:
            raise GlossaryParseError(f"empty full_form for term {term!r}", row=line_idx)
        if not definition:
            raise GlossaryParseError(f"empty definition for term {term!r}", row=line_idx)
        if len(term) > MAX_TERM_LEN:
            raise GlossaryParseError(f"term too long (>{MAX_TERM_LEN} chars)", row=line_idx)
        if len(full_form) > MAX_FULL_FORM_LEN:
            raise GlossaryParseError(f"full_form too long (>{MAX_FULL_FORM_LEN} chars)", row=line_idx)
        if len(definition) > MAX_DEFINITION_LEN:
            raise GlossaryParseError(f"definition too long (>{MAX_DEFINITION_LEN} chars)", row=line_idx)
        if term in seen_terms:
            raise GlossaryParseError(f"duplicate term in CSV: {term!r}", row=line_idx)
        seen_terms.add(term)
        rows.append({
            "term": term,
            "full_form": full_form,
            "definition": definition,
            "aliases": _parse_aliases(row.get("aliases", "")),
        })
        if len(rows) > MAX_TERMS_PER_UPLOAD:
            raise GlossaryParseError(
                f"too many rows (>{MAX_TERMS_PER_UPLOAD}); split the CSV"
            )
    return rows


class GlossaryTermService(CommonService):
    model = GlossaryTerm

    @classmethod
    @DB.connection_context()
    def list_for_kb(cls, kb_id: str) -> list[dict]:
        objs = cls.model.select().where(cls.model.kb_id == kb_id).order_by(cls.model.term)
        return [o.to_dict() for o in objs]

    @classmethod
    @DB.connection_context()
    def delete_term(cls, kb_id: str, term_id: str) -> int:
        # kb_id is in the WHERE clause to prevent cross-KB deletion via id leak.
        return cls.model.delete().where(
            (cls.model.id == term_id) & (cls.model.kb_id == kb_id)
        ).execute()

    @classmethod
    @DB.connection_context()
    def upsert_many(cls, kb_id: str, tenant_id: str, created_by: str,
                    rows: list[dict]) -> dict:
        """Insert new terms; update existing ones (matched by (kb_id, term)).

        Returns a small report dict ``{"inserted": N, "updated": M}`` so the UI
        can show "X new, Y updated"."""
        now_ts = current_timestamp()
        now_dt = datetime_format(datetime.now())
        inserted = 0
        updated = 0
        for row in rows:
            existing = cls.model.select().where(
                (cls.model.kb_id == kb_id) & (cls.model.term == row["term"])
            ).first()
            if existing is None:
                try:
                    cls.model.create(
                        id=get_uuid(),
                        kb_id=kb_id,
                        tenant_id=tenant_id,
                        created_by=created_by,
                        term=row["term"],
                        full_form=row["full_form"],
                        definition=row["definition"],
                        aliases=row.get("aliases", []),
                        create_time=now_ts,
                        create_date=now_dt,
                        update_time=now_ts,
                        update_date=now_dt,
                    )
                    inserted += 1
                except IntegrityError:
                    # Lost race with a concurrent upload: fall through to update.
                    cls.model.update(
                        full_form=row["full_form"],
                        definition=row["definition"],
                        aliases=row.get("aliases", []),
                        update_time=now_ts,
                        update_date=now_dt,
                    ).where(
                        (cls.model.kb_id == kb_id) & (cls.model.term == row["term"])
                    ).execute()
                    updated += 1
            else:
                cls.model.update(
                    full_form=row["full_form"],
                    definition=row["definition"],
                    aliases=row.get("aliases", []),
                    update_time=now_ts,
                    update_date=now_dt,
                ).where(cls.model.id == existing.id).execute()
                updated += 1
        return {"inserted": inserted, "updated": updated}

    @classmethod
    def render_for_prompt(cls, kb_id: str) -> str:
        """Render a KB's glossary as a compact text block for LLM injection.

        Format keeps it scannable for the model and cheap in tokens:

            ## מילון מונחים
            - דנ"פ (דמי ניהול פקדון): עמלה שמשלם הלקוח...
            - פצ"ל (פדיון צמוד למדד): תעודה שערכה משתנה...

        Returns "" when the KB has no glossary so callers can `if block:` cheaply.
        """
        terms = cls.list_for_kb(kb_id)
        if not terms:
            return ""
        lines = ["## מילון מונחים"]
        for t in terms:
            lines.append(f"- {t['term']} ({t['full_form']}): {t['definition']}")
        return "\n".join(lines)
