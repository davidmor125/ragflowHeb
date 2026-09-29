# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFlow is an open-source RAG engine based on deep document understanding. The repo is a polyglot full-stack monorepo:

- **Python backend** (**Quart**, not Flask — see "Backend layout" below) under `api/`, `rag/`, `agent/`, `deepdoc/`, `common/`, `mcp/` — the production runtime.
- **Go backend** under `cmd/`, `internal/`, `admin/` (module `ragflow` at the repo root via `go.mod`) — an in-progress reimplementation / companion server. Both backends share schemas with the same MySQL/ES/Redis/MinIO infra.
- **TypeScript/React frontend** under `web/` — Vite + shadcn/ui + Tailwind + Zustand + TanStack Query + react-router. Has its own `web/CLAUDE.md` with stricter rules; **read it before touching anything in `web/`** (notably: do not modify `web/src/components/ui/`).
- **Helm chart** under `helm/`, **admin console** under `admin/`, **MCP server/client** under `mcp/`, **Python SDK** under `sdk/python/`.

Note: `AGENTS.md` and `.github/copilot-instructions.md` exist for other AI agents and are *partially out of date*. `AGENTS.md` describes the frontend as UmiJS (it was migrated to Vite) and claims "Python 3.10+" (`pyproject.toml` pins `>=3.12,<3.15`). `.github/copilot-instructions.md` tells you to `pip install -r requirements.txt` — there is no such file; the project uses `uv` + `pyproject.toml`. Trust this file and the actual code over those.

This working copy **is** a git repository (branch `main`, two commits: `8954cb7 "Initial commit: RAGFlow working tree snapshot"` and `c10e156 "Update CLAUDE.md and add external API integration guide"`). It is a local snapshot, not a clone of the upstream `infiniflow/ragflow` history — so there's no meaningful commit log or remote to compare against, and rebase/bisect-style workflows won't have history to work with. Ordinary `git` commands work; commit or push only when the user asks.

**The retrieval/parsing path carries deliberate local changes** (not upstream code), committed on branch `fix/hebrew-rag-parsing-retrieval`: `common/text_utils.py`, `deepdoc/parser/excel_parser.py`, `deepdoc/parser/html_parser.py`, `rag/app/naive.py`, `rag/flow/tokenizer/tokenizer.py`, `rag/llm/rerank_model.py`, `rag/nlp/__init__.py`, `rag/nlp/query.py`, `rag/nlp/search.py`, `rag/prompts/generator.py`, `rag/svr/task_executor.py`, plus `Dockerfile.patched`. Tests are in `test/unit_test/common/test_text_utils.py` and `test/unit_test/rag/test_docx_and_table_parsing.py`. Under pytest's `filterwarnings = error`, importing `rag.app.naive` fails on xgboost's `pkg_resources` UserWarning; run them with `uv run --no-sync --with pytest --with pytest-asyncio --with "setuptools<81" python -m pytest <files> -W "ignore::UserWarning" -W "ignore::FutureWarning"`. **The running Docker stack does not see edits to these files automatically**: `Dockerfile.patched` layers them onto the stock `infiniflow/ragflow:v0.25.0` image (`docker build -f Dockerfile.patched -t infiniflow/ragflow:v0.25.0-patched .`, which takes seconds; a full `Dockerfile` rebuild takes hours). Its comments explain each fix, and it also installs `python-bidi` (Hebrew PDFs), which the released image lacks. When you change a file on this path, add a `COPY` line for it to `Dockerfile.patched` if it isn't already there, then rebuild and restart the container.

**This snapshot tree is newer than the v0.25.0 image, even where git shows no local change.** That is why `Dockerfile.patched` also copies the *unmodified* `deepdoc/parser/pdf_parser.py` (the image has no `reorder_bidi()` call sites), `common/constants.py` (`MAXIMUM_PAGE_NUMBER`) and `common/settings.py` (`VISION_RAG_ENABLED`): the patched modules import symbols that don't exist in the image. If a patched module starts importing something new, check that the symbol exists in v0.25.0. If it doesn't, `COPY` its support file too. Otherwise the container fails with `ImportError`/`AttributeError`, sometimes only on one code path (e.g. docs that reach image handling). Note also that `reorder_bidi()` is not idempotent. Any new call site must gate on `common/text_utils.py::looks_visual_order`.

`BANK_INSTALLATION_GUIDE.md` (untracked, Hebrew) is the air-gapped install guide for deploying this patched image on the bank's servers. Keep it in sync when you change the image tag, the model list, ports or the `Dockerfile.patched` build step. Re-parse affected docs only when the change affects indexing. Before editing any of these files, run `git diff <file>` to see what already diverged — and don't `git checkout`/revert them casually. (This list drifts; `git status` is authoritative.)

## Architecture — what isn't obvious from the tree

### Two-process Python backend

The Python runtime is **not just an API server**. `docker/launch_backend_service.sh` spawns:

1. `api/ragflow_server.py` — the API process; it imports the already-constructed `app` from `api/apps/`.
2. `rag/svr/task_executor.py` — N background workers (controlled by `WS` env var) that consume document-ingestion / chunking / embedding tasks from Redis. The API enqueues tasks; the executors do the heavy work.

Anything that touches parsing, chunking, embedding, or graph construction runs in the executor, not the API process. When debugging "the doc was uploaded but never indexed," check the executor logs, not the server. Other long-running services in `rag/svr/`: `cache_file_svr.py`, `sync_data_source.py`, `discord_svr.py`.

### Backend layout (Python)

- `api/apps/` — **Quart** blueprints (`api/apps/__init__.py:22` does `from quart import Blueprint, Quart, ...`). Endpoint routing lives here. Quart is async-native and API-compatible with Flask, so handlers are `async def` and Flask-shaped snippets from docs/StackOverflow usually port over — but `import flask` appears nowhere in `api/`, so don't add it, and don't call blocking I/O directly in a handler. Use `thread_pool_exec` from `common/misc_utils.py` for the sync→async bridge. This is also why ruff enables the `ASYNC` rule sets.
- `api/db/services/` — service layer (business logic, transaction boundaries).
- `api/db/db_models.py` — Peewee ORM models (single file, authoritative schema).
- `rag/llm/` — model abstractions (`chat_model.py`, `embedding_model.py`, `rerank_model.py`, `cv_model.py`, `ocr_model.py`, `tts_model.py`, `sequence2txt_model.py`). Adding a provider means adding a class to the relevant module and registering it.
- `rag/app/` — **one module per chunking method** (`naive`, `manual`, `paper`, `book`, `laws`, `presentation`, `qa`, `table`, `resume`, `picture`, `audio`, `email`, `tag`, `one`). A dataset's `parser_id` selects one of these via the `FACTORY` dict in `rag/svr/task_executor.py` (~line 85), which then calls the module's `chunk()`. This is the entry point when a task is "chunk this document a different way" — start at `FACTORY`, not in `api/`. Note two non-1:1 mappings: `"general"` (the common default `parser_id`) and `ParserType.KG` both resolve to `naive` — there is no `general.py` or `kg.py`.
- `rag/flow/` — orchestrable ingestion pipeline (chunking, parsing, tokenization stages).
- `rag/graphrag/` — knowledge-graph construction and querying.
- `rag/nlp/`, `rag/prompts/` — tokenization helpers and prompt templates.
- `agent/component/` — agent canvas building blocks (`llm`, `categorize`, `iteration`, `loop`, `switch`, `invoke`, etc.); `agent/canvas.py` is the executor; `agent/templates/` ships pre-built agents.
- `deepdoc/parser/` and `deepdoc/vision/` — PDF/Office parsing, OCR, layout/table recognition (the "deep document understanding" that distinguishes RAGFlow).
- `common/` — shared Python utilities. **It is 100% Python** (`find common -name '*.go'` returns nothing) — the Go code lives in `cmd/`, `internal/`, and `admin/`. The heavily-imported modules: `constants.py` (the `LLMType` / `StatusEnum` / `RetCode` / `ParserType` enum vocabulary the whole codebase speaks), `settings.py` (global mutable config), `misc_utils.py` (`get_uuid`, `thread_pool_exec` — the sync→async bridge), `connection_utils.py` (the `@timeout` decorator wrapping every component `_invoke`, default 600s).
  - `common/doc_store/` — connection pools/base classes for the doc engines. Note this reveals a **fourth** engine beyond the ES/Infinity/OpenSearch trio: **OceanBase** (`ob_conn_base.py`).
  - `common/data_source/` — an easily-missed subsystem of ~25 external ingestion connectors (Confluence, Jira, Slack, SharePoint, Google Drive, Notion, GitHub/GitLab, IMAP/Gmail, RDBMS…) driven by `connector_runner.py` against the `interfaces.py` contract.

### Go backend (`cmd/` + `internal/`)

`go.mod` module name is `ragflow`, Go 1.25. Three entry points in `cmd/`:
- `cmd/server_main.go` — main API server (gin + gorm + go-redis + elastic v8 + minio).
- `cmd/admin_server.go` — admin console backend.
- `cmd/ragflow_cli.go` — CLI.

`internal/` follows a layered structure: `handler/` (HTTP) → `service/` → `dao/` (gorm) → `storage/`. Other packages: `admin/`, `binding/`, `cache/`, `cli/`, `common/`, `cpp/`, `engine/`, `entity/`, `logger/`, `router/`, `server/`, `tokenizer/`, `utility/`. Tests are run via `run_go_tests.sh`, which iterates an explicit `PACKAGES` list — `internal/binding`, `internal/service`, and `internal/utility` are **commented out** because they fail. Don't assume `go test ./...` passes; add a package back to that list only if you've made it green. The list also names `./internal/model/...`, which does not exist as a directory (the entity package is `internal/entity/`) — that entry emits a "matched no packages" warning that is pre-existing, not something you broke.

**The Go toolchain is not installed on this dev machine** (`go` is absent from PATH in both PowerShell and the bash shim). Go build/test commands will fail with "command not found" until it's installed — that's environmental, not a code problem. Python and the frontend are the practically runnable stacks here.

When writing Go, follow the naming conventions in `.agents/rules/named.md` (package/file/interface/error naming — e.g. `ErrNotFound`, `-er` interfaces, no `util` packages). `.agents/skills/go-naming/` packages the same rules as a skill for other agents.

### Skills

`.claude/skills/rag-expert/` (untracked) is a project skill for auditing this deployment's retrieval quality — empty/irrelevant results, missing chunks, chunking-parsing problems, embedding/reranker config, Hebrew cross-language queries. It encodes the same gotchas as the "Retrieval gotchas" section below plus concrete diagnostic steps. Invoke it before hand-rolling a retrieval investigation or when reviewing changes to `rag/nlp/`, `rag/app/`, `deepdoc/parser/`, or `/api/v1/retrieval`.

### Storage backends are swappable

- **Doc engine**: Elasticsearch (default), Infinity, or OpenSearch — selected by `DOC_ENGINE` in `docker/.env`. Switching requires `docker compose down -v && docker compose up -d` (the `-v` drops volumes).
- **Object storage**: MinIO (default) or S3 / Azure / OSS / OpenDAL.

Service-layer code should always go through the abstractions in `rag/utils/` (Python) or `internal/storage/` (Go), never talk to a specific engine directly.

## Commands

### Python backend

```bash
# First-time setup (Python 3.12; pyproject pins >=3.12,<3.15)
uv sync --python 3.12 --all-extras
uv run python3 download_deps.py
pre-commit install

# Bring up infra (MySQL / ES / Redis / MinIO)
docker compose -f docker/docker-compose-base.yml up -d

# Run API + task executors (Linux/macOS)
source .venv/bin/activate
export PYTHONPATH=$(pwd)
bash docker/launch_backend_service.sh        # WS=N controls executor count

# On Windows, run the two processes separately:
#   python api/ragflow_server.py
#   python rag/svr/task_executor.py 0
```

### Tests (Python)

`pyproject.toml` configures pytest to collect only from `test/`. Subtrees:
- `test/unit_test/` — pure unit tests.
- `test/testcases/test_http_api/` and `test/testcases/test_sdk_api/` — integration tests that hit a running RAGFlow stack via HTTP or the Python SDK. They expect `HOST_ADDRESS` (default `http://127.0.0.1:9380`) and accept a custom `--level` flag (`p0`/`p1`/`p2`/`p3`) to filter by priority marker. `--level` is registered in `test/testcases/conftest.py` — passing it outside that subtree is an "unrecognized argument" error; use `-m p1` for unit tests instead.
- `test/playwright/` — Playwright UI tests.

Useful invocations:

```bash
uv run pytest                                         # all unit tests
uv run pytest test/unit_test/<path>.py::TestX::test_y # single test
uv run pytest -m p1                                   # priority filter (markers: p0/p1/p2/p3, smoke, auth, asyncio)
pytest -s --tb=short --level=p2 test/testcases/test_http_api    # integration vs running stack
DOC_ENGINE=infinity pytest --level=p2 test/testcases/test_sdk_api  # against Infinity
```

`pyproject.toml` sets `filterwarnings = ["error", "ignore::DeprecationWarning"]` — a stray warning fails the test unless it's a `DeprecationWarning`. Note `addopts` also carries `--disable-warnings`, which only suppresses the summary *report*, not the `error` filter itself; a non-deprecation warning still fails. `addopts` is `-v --strict-markers --tb=short --disable-warnings --color=yes`. Markers are strict — the registered set is exactly `p0`, `p1`, `p2`, `p3`, `smoke`, `auth`, `asyncio`; register new ones in `pyproject.toml` before using.

### Lint / format (Python)

`ruff` is configured with `line-length = 200`, extra-selects `ASYNC`/`ASYNC1` (so misuse of async/await is caught), and ignores `E402` (module-level import not at top — common in this codebase, don't "fix" it). `.venv` and `rag/svr/discord_svr.py` are excluded.

`ruff` is **not** a project dependency and is not installed in `.venv` — it's supplied by pre-commit's own managed environment. A bare `ruff check` fails with "command not found" on this machine. Use one of:

```bash
uvx ruff check          # no install needed
uvx ruff format
pre-commit run ruff --all-files        # exactly what the hook runs
```

`.pre-commit-config.yaml` runs `ruff --fix` and `ruff-format` on commit, plus whitespace/EOF/merge-conflict hooks — so committing can rewrite files under you. Run the formatter before committing to avoid surprise diffs.

### Frontend

```bash
cd web
npm install
npm run dev          # vite dev server, --host enabled
npm run build        # production build
npm run lint         # eslint (ts/tsx)
npm run test         # jest --coverage
npm run type-check   # tsc --noEmit
npm run storybook    # component dev on :6006
```

Read `web/CLAUDE.md` first for project-specific rules (CSS-debugging methodology, i18n key placement rules, the lock on `src/components/ui/`).

### Go

```bash
go build ./cmd/...
go test ./internal/handler/...           # single package
bash run_go_tests.sh                     # the curated set that passes
```

### Docker (full stack)

```bash
cd docker
docker compose -f docker-compose.yml up -d
docker logs -f ragflow-server
docker build --platform linux/amd64 -f Dockerfile -t infiniflow/ragflow:nightly ..
```

`docker/` ships several compose variants: `docker-compose.yml` (full stack), `docker-compose-base.yml` (infra only), `docker-compose-macos.yml`, and `docker-compose-CN-oc9.yml` (CN mirror). Pick the one matching the platform/mirror rather than editing the default.

### Windows note

The command blocks above assume a POSIX shell. On Windows (the primary dev platform here), `source .venv/bin/activate` / `export VAR=...` don't apply — use `.venv\Scripts\Activate.ps1` and `$env:VAR = "..."`, and run the two Python processes separately (see the Python-backend block above) since `docker/launch_backend_service.sh` is a bash script.

## Key configuration files

- `docker/.env` — runtime config: `DOC_ENGINE`, `RAGFLOW_IMAGE`, ports, embedding/TEI profile, etc. Created from `docker/.env.example`.
- `docker/service_conf.yaml.template` — backend service config rendered into the container.
- `pyproject.toml` — Python deps, ruff, pytest config, `[tool.uv.index]` points at the Aliyun mirror (override if you're outside CN).
- `web/package.json` — frontend scripts and deps.
- `go.mod` — module `ragflow`, Go 1.25.0. Note the `replace` directive pinning `github.com/infiniflow/infinity-go-sdk` to a pseudo-version of `github.com/infiniflow/infinity/go`.

## Repo-root scratch files

The repo root holds ~400 entries, of which **~250 are `_`-prefixed scratch files** (`_check_*.py`, `_audit_*.json`, `_agent*_progress.txt`, …) plus unprefixed leftovers like `test_50_questions.py`, `dump_all_chunks.py`, `req_*.json`, `resp_*.json`, `test_report*.txt`. These are **not** part of the package or test suite (`pyproject.toml`'s `testpaths = ["test"]` excludes them). Treat them as throwaway unless a specific task references one — don't lint, refactor, or "clean them up" proactively.

Practical consequence: **root-level globs are nearly useless for code search.** A `*.py` glob at the root returns 237 files, almost all scratch. Search inside `api/`, `rag/`, `agent/`, `deepdoc/`, `common/`, `internal/`, or `web/src/` instead of the repo root.

Root `.md` files are similarly mixed: `README*.md` (11 translations), `SECURITY.md`, and the live-verified docs called out in the next paragraph are real; `CLIENT_EVAL_*.md`, `EVAL_*.md`, `HEADING_CHUNK_FIX_BRIEF.md`, `RAGFLOW_API_GUIDE.md`, `RAGFLOW_DATASET_SETTINGS.md`, and `_*.md` are investigation notes of varying staleness.

**Exception — keep these repo-root docs:** `BANK_INSTALLATION_GUIDE.md` (see above), `Dockerfile.patched`, and the following. `SERVICE_CONTRACT.md` (plus `SERVICE_CONTRACT_BRIEF.md` / `_CONTINUE.md`) and `EXTERNAL_API_GUIDE.md` are deliberate, **live-verified** references for the running v0.25.0 Docker stack, not scratch. `SERVICE_CONTRACT.md` is the authoritative API contract — trust it over the official RAGFlow docs where they conflict (e.g. `/chats` response fields, markdown `VISION`, cross-language retrieval). `EXTERNAL_API_GUIDE.md` (Hebrew) is an integration guide for calling the local stack at `http://localhost:9380/api/v1` from an external project. When working against the live API, consult these before assuming endpoint behavior.

## Retrieval gotchas (verified against the live stack)

- **`top_k` is not "how many results"** — in `POST /api/v1/retrieval` it's the vector-search *candidate pool* (default **1024**, see `api/apps/sdk/doc.py` ~line 438). `page_size` controls how many chunks come back. Passing `top_k=5` shrinks the pool to 5 and typically yields 0–1 chunks; it looks like a broken index but isn't.
- **`available_int` silently hides chunks.** `rag/nlp/search.py` (~line 437) hardcodes `"available_int": 1` into every retrieval request. Chunks stored with `available_int: 0` are indexed and counted in the dataset's `chunk_count`, but are *invisible to retrieval*. A dataset reporting N chunks while retrieval returns `total=0` almost always means the chunks were disabled, not that parsing failed. Check with a direct ES query before re-parsing anything.
- **Query in the corpus language.** With `bge-m3@Ollama` over a Hebrew corpus, English queries frequently return nothing. Assistants set `prompt_config.cross_languages` (e.g. `["Hebrew","English"]`) to translate the query first — standalone `/retrieval` calls do *not* do this unless you pass it.
- **Hebrew via shell `curl` breaks**; use Python/httpx. On Windows also wrap stdout (`io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")`) or printing Hebrew answers dies with a `cp1252` `UnicodeEncodeError`.
- **ES is authenticated**: `curl -u elastic:infini_rag_flow http://localhost:1200/...` (password from `docker/.env`). The tenant index is `ragflow_<tenant_id>`.
- **Parent-child: retrieval returns the PARENT, children are what gets matched.** Children (`mom_id` set) are cut per line and embedded; `retrieval_by_children` swaps in the hidden parent (`available_int: 0`) for the LLM, and for the top 2 parents appends same-section neighbours (`RAG_NEIGHBOR_EXPAND=0` disables). Parent ids are `hash(doc_id + text)`, and `content_with_weight` is not indexed in ES (search it via `content_ltks` or scroll).
- **HTML chunks carry `⟦נוהל: <procedure> | <section path>⟧` lines** (parent-child datasets only, `HtmlParser.parts(with_context=True)`), and tables carry the same text as `<caption>`. They are there on purpose: they are what lets a 40-char child match its procedure. `title_tks`/`doc_title_kwd` hold the procedure name taken from the file's first line; `docnm_kwd` stays the file name.
- **The prompt budget is the model's `tenant_llm.max_tokens`, counted in cl100k**, which over-counts Hebrew about 2x. It is set to 32768 for `gemma4:31b-cloud`; 8192 silently dropped the chunk holding the answer. RAGFlow never sends this value to Ollama as `num_ctx`, so don't raise it for a *local* model without also raising Ollama's context.
- **`/api/v1/retrieval` with `keyword: true` calls the tenant's DEFAULT chat model** (a local model here), not the chat's model. Under executor load it hangs, so omit `keyword` when probing retrieval by hand.
- **`@timeout` in `common/connection_utils.py` enforces nothing unless `ENABLE_TIMEOUT_ASSERTION` is set.** Don't rely on it to bound a call; add an explicit wait limit (see `figure_parser.py`).
