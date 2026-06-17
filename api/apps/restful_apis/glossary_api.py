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
"""REST endpoints for per-KB banking glossary.

Routes (mounted under the project's standard /v1 prefix):
    POST   /datasets/<kb_id>/glossary/upload   — bulk upload CSV
    GET    /datasets/<kb_id>/glossary          — list all terms in KB
    DELETE /datasets/<kb_id>/glossary/<id>     — remove one term
    GET    /datasets/glossary/template         — download blank CSV template
"""

import logging

from quart import request, Response

from api.apps import login_required
from api.utils.api_utils import (
    add_tenant_id_to_kwargs,
    get_error_argument_result,
    get_error_data_result,
    get_result,
)
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.glossary_term_service import (
    GlossaryParseError,
    GlossaryTermService,
    parse_csv,
)


# CSV template returned by GET /datasets/glossary/template. Two example rows
# in Hebrew so a banking analyst sees the expected shape immediately.
CSV_TEMPLATE = (
    "term,full_form,definition,aliases\r\n"
    '"דנ""פ","דמי ניהול פקדון","עמלה שמשלם הלקוח עבור אחזקת ניירות ערך בבנק","דנפ;ד.נ.פ"\r\n'
    '"בונדס","איגרות חוב של מדינת ישראל","תעודות חוב שמנפיקה מדינת ישראל בחו""ל","Bonds;ישראל בונדס"\r\n'
)


def _verify_kb_owned_by_tenant(kb_id: str, tenant_id: str):
    """Return (ok, kb_or_error_message). Centralized so every route enforces it."""
    e, kb = KnowledgebaseService.get_by_id(kb_id)
    if not e:
        return False, "knowledge base not found"
    if kb.tenant_id != tenant_id:
        # Don't leak existence to other tenants — same 404-equivalent message.
        return False, "knowledge base not found"
    return True, kb


@manager.route("/datasets/glossary/template", methods=["GET"])  # noqa: F821
@login_required
def glossary_template():
    """Download a blank CSV template (UTF-8 with BOM so Excel opens it cleanly)."""
    body = "﻿" + CSV_TEMPLATE  # BOM
    return Response(
        body,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="glossary_template.csv"'},
    )


@manager.route("/datasets/<kb_id>/glossary", methods=["GET"])  # noqa: F821
@login_required
@add_tenant_id_to_kwargs
def list_glossary(kb_id: str, tenant_id: str = None):
    ok, kb_or_msg = _verify_kb_owned_by_tenant(kb_id, tenant_id)
    if not ok:
        return get_error_data_result(message=kb_or_msg)
    try:
        terms = GlossaryTermService.list_for_kb(kb_id)
        return get_result(data={"terms": terms, "count": len(terms)})
    except Exception as e:
        logging.exception(e)
        return get_error_data_result(message="Internal server error")


@manager.route("/datasets/<kb_id>/glossary/upload", methods=["POST"])  # noqa: F821
@login_required
@add_tenant_id_to_kwargs
async def upload_glossary(kb_id: str, tenant_id: str = None):
    ok, kb_or_msg = _verify_kb_owned_by_tenant(kb_id, tenant_id)
    if not ok:
        return get_error_data_result(message=kb_or_msg)

    content_type = request.content_type or ""
    if "multipart/form-data" not in content_type:
        return get_error_argument_result("expected multipart/form-data with a 'file' field")
    files = await request.files
    if "file" not in files:
        return get_error_argument_result("missing 'file' part")
    file_obj = files["file"]
    if not file_obj.filename:
        return get_error_argument_result("uploaded file has no filename")

    try:
        raw = file_obj.read()
    except Exception as e:
        return get_error_argument_result(f"failed to read upload: {e}")

    try:
        rows = parse_csv(raw)
    except GlossaryParseError as e:
        msg = str(e) + (f" (line {e.row})" if e.row else "")
        return get_error_argument_result(msg)
    except Exception as e:
        logging.exception(e)
        return get_error_data_result(message="failed to parse CSV")

    if not rows:
        return get_error_argument_result("CSV contained no usable rows")

    try:
        report = GlossaryTermService.upsert_many(
            kb_id=kb_id,
            tenant_id=tenant_id,
            created_by=tenant_id,
            rows=rows,
        )
        report["total"] = len(rows)
        return get_result(data=report)
    except Exception as e:
        logging.exception(e)
        return get_error_data_result(message="Internal server error")


@manager.route("/datasets/<kb_id>/glossary/<term_id>", methods=["DELETE"])  # noqa: F821
@login_required
@add_tenant_id_to_kwargs
def delete_glossary_term(kb_id: str, term_id: str, tenant_id: str = None):
    ok, kb_or_msg = _verify_kb_owned_by_tenant(kb_id, tenant_id)
    if not ok:
        return get_error_data_result(message=kb_or_msg)
    try:
        deleted = GlossaryTermService.delete_term(kb_id, term_id)
        if deleted == 0:
            return get_error_data_result(message="term not found")
        return get_result(data={"deleted": deleted})
    except Exception as e:
        logging.exception(e)
        return get_error_data_result(message="Internal server error")
