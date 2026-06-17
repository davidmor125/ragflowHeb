# Banking Glossary (per-KB)

Upload a CSV of banking abbreviations and their definitions to a knowledge
base. Every chat that uses the KB will have the glossary appended to the
LLM system prompt, so the model knows what terms like `דנ"פ` or `בונדס`
mean even when the retrieved chunks don't spell them out.

## CSV format

UTF-8, header row required. Columns:

| Column | Required | Notes |
|---|---|---|
| `term` | yes | Surface form as it appears in documents (e.g. `דנ"פ`). Unique per KB. |
| `full_form` | yes | Expanded form (e.g. `דמי ניהול פקדון`). |
| `definition` | yes | One short sentence injected into the LLM prompt. |
| `aliases` | no | Semicolon-separated alternate spellings (e.g. `דנפ;ד.נ.פ`). |

Aliases use **semicolon**, not comma — Hebrew terms routinely contain commas
inside quoted fields. Excel saves CSV as UTF-8-with-BOM by default; the
parser strips the BOM.

### Example

```csv
term,full_form,definition,aliases
"דנ""פ","דמי ניהול פקדון","עמלה שמשלם הלקוח עבור אחזקת ניירות ערך בבנק","דנפ;ד.נ.פ"
"בונדס","איגרות חוב של מדינת ישראל","תעודות חוב שמנפיקה מדינת ישראל בחו""ל","Bonds;ישראל בונדס"
```

## REST API

All routes are scoped to a knowledge base and require a logged-in tenant
that owns the KB.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/datasets/glossary/template` | Download a blank CSV template (with example rows). |
| `GET` | `/v1/datasets/<kb_id>/glossary` | List all terms in the KB. |
| `POST` | `/v1/datasets/<kb_id>/glossary/upload` | Upload a CSV (multipart, field name `file`). |
| `DELETE` | `/v1/datasets/<kb_id>/glossary/<term_id>` | Remove a single term. |

Upload is **additive**: existing terms with the same `(kb_id, term)` are
updated; new terms are inserted; terms that exist in the DB but are absent
from the CSV are left alone. To remove a term, use the `DELETE` route.

### Upload response

```json
{ "inserted": 12, "updated": 3, "total": 15 }
```

### Validation errors

The parser fails fast on the first invalid row and returns a 400 with the
1-based line number, so the UI can highlight it. Cases caught:

- Not valid UTF-8.
- Missing any of the required header columns.
- Empty `term`, `full_form`, or `definition` in a row.
- Duplicate `term` within the same CSV.
- A field exceeding its length cap (`term` 128, `full_form` 256,
  `definition` 1000).
- More than 5,000 rows in one upload.

Blank trailing rows (Excel adds them) are silently skipped.

## How the glossary reaches the model

When a chat is sent, [`api/db/services/dialog_service.py`](../../api/db/services/dialog_service.py)
collects the glossary for every KB attached to the dialog and appends a
block to the system prompt:

```
## מילון מונחים
- דנ"פ (דמי ניהול פקדון): עמלה שמשלם הלקוח עבור אחזקת ניירות ערך בבנק
- בונדס (איגרות חוב של מדינת ישראל): תעודות חוב שמנפיקה מדינת ישראל בחו"ל
```

KBs without a glossary contribute nothing — there is no per-request cost
when the feature isn't used. A failure inside the glossary lookup never
breaks the chat; it is logged and skipped.

## Storage

Terms live in the `glossary_term` table
([`api/db/db_models.py`](../../api/db/db_models.py), `class GlossaryTerm`).
Each row carries `kb_id`, `tenant_id`, `term`, `full_form`, `definition`,
and a JSON `aliases` list. The unique index on `(kb_id, term)` is what
makes upload idempotent.

The table is created automatically on backend startup by
`init_database_tables`.

## Code map

| Concern | File |
|---|---|
| DB model | [`api/db/db_models.py`](../../api/db/db_models.py) — `class GlossaryTerm` |
| Service + CSV parser | [`api/db/services/glossary_term_service.py`](../../api/db/services/glossary_term_service.py) |
| REST endpoints | [`api/apps/restful_apis/glossary_api.py`](../../api/apps/restful_apis/glossary_api.py) |
| Prompt injection | [`api/db/services/dialog_service.py`](../../api/db/services/dialog_service.py) — search for `glossary_blocks` |
| Unit tests | [`test/unit_test/api/db/services/test_glossary_term_service.py`](../../test/unit_test/api/db/services/test_glossary_term_service.py) |

## Related: synonym dictionary

A separate, project-wide synonym mechanism already exists for query
expansion at retrieval time: [`rag/res/synonym.json`](../../rag/res/synonym.json)
loaded by [`rag/nlp/synonym.py`](../../rag/nlp/synonym.py). That file was
patched at the same time to be read as UTF-8 (it had been opening with the
platform default encoding, which broke Hebrew on Windows). Populating it
with Hebrew banking abbreviations expands user queries automatically — a
complementary lever to the per-KB glossary documented above.

## What this feature does NOT do (yet)

- **No UI.** Upload/list/delete must be hit via the REST API directly until
  a settings tab is added to the KB page in `web/src/pages/dataset/`.
- **No chunk-level enrichment.** The glossary is injected at generation
  time only; document chunks are not augmented with definitions during
  ingestion.
- **No global glossary.** Each KB has its own. A shared dictionary across
  KBs would need either a separate table or a `kb_id IS NULL` convention.
