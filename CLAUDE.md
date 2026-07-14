# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFlow is an open-source RAG engine based on deep document understanding. The repo is a polyglot full-stack monorepo:

- **Python backend** (Flask) under `api/`, `rag/`, `agent/`, `deepdoc/`, `common/`, `mcp/` — the production runtime.
- **Go backend** under `cmd/`, `internal/`, `common/` (Go also lives at the repo root via `go.mod`) — an in-progress reimplementation / companion server. Both backends share schemas with the same MySQL/ES/Redis/MinIO infra.
- **TypeScript/React frontend** under `web/` — Vite + shadcn/ui + Tailwind + Zustand + TanStack Query + react-router. Has its own `web/CLAUDE.md` with stricter rules; **read it before touching anything in `web/`** (notably: do not modify `web/src/components/ui/`).
- **Helm chart** under `helm/`, **admin console** under `admin/`, **MCP server/client** under `mcp/`, **Python SDK** under `sdk/python/`.

Note: `AGENTS.md` and `.github/copilot-instructions.md` exist for other AI agents and are *partially out of date* (e.g. they describe the frontend as UmiJS — it has been migrated to Vite). Trust this file and the actual code over those.

This working copy **is** a git repository (branch `main`, currently a single snapshot commit `8954cb7 "Initial commit: RAGFlow working tree snapshot"`). It is a local snapshot, not a clone of the upstream `infiniflow/ragflow` history — so there's no meaningful commit log or remote to compare against, and rebase/bisect-style workflows won't have history to work with. Ordinary `git` commands work; commit or push only when the user asks.

## Architecture — what isn't obvious from the tree

### Two-process Python backend

The Python runtime is **not just an API server**. `docker/launch_backend_service.sh` spawns:

1. `api/ragflow_server.py` — Flask API (one process).
2. `rag/svr/task_executor.py` — N background workers (controlled by `WS` env var) that consume document-ingestion / chunking / embedding tasks from Redis. The API enqueues tasks; the executors do the heavy work.

Anything that touches parsing, chunking, embedding, or graph construction runs in the executor, not the API process. When debugging "the doc was uploaded but never indexed," check the executor logs, not the server. Other long-running services in `rag/svr/`: `cache_file_svr.py`, `sync_data_source.py`, `discord_svr.py`.

### Backend layout (Python)

- `api/apps/` — Flask blueprints. Endpoint routing lives here.
- `api/db/services/` — service layer (business logic, transaction boundaries).
- `api/db/db_models.py` — Peewee ORM models (single file, authoritative schema).
- `rag/llm/` — model abstractions (chat / embedding / rerank / TTS / sequence2txt). Adding a provider means adding a class here and registering it.
- `rag/flow/` — orchestrable ingestion pipeline (chunking, parsing, tokenization stages).
- `rag/graphrag/` — knowledge-graph construction and querying.
- `rag/nlp/`, `rag/prompts/` — tokenization helpers and prompt templates.
- `agent/component/` — agent canvas building blocks (`llm`, `categorize`, `iteration`, `loop`, `switch`, `invoke`, etc.); `agent/canvas.py` is the executor; `agent/templates/` ships pre-built agents.
- `deepdoc/parser/` and `deepdoc/vision/` — PDF/Office parsing, OCR, layout/table recognition (the "deep document understanding" that distinguishes RAGFlow).
- `common/` — shared utilities used by **both** Python (`*.py` files) and Go (`common/data_source/`, `common/doc_store/` are Go subdirs). When editing, check the file extension; the directory is mixed.

### Go backend (`cmd/` + `internal/`)

`go.mod` module name is `ragflow`, Go 1.25. Three entry points in `cmd/`:
- `cmd/server_main.go` — main API server (gin + gorm + go-redis + elastic v8 + minio).
- `cmd/admin_server.go` — admin console backend.
- `cmd/ragflow_cli.go` — CLI.

`internal/` follows a layered structure: `handler/` (HTTP) → `service/` → `dao/` (gorm) → `storage/`. Other packages: `engine/`, `tokenizer/`, `cache/`, `router/`, `cli/`, `binding/`, `cpp/`. Tests are run via `run_go_tests.sh` (some packages — `binding`, `service`, `utility` — are deliberately excluded; check the script before assuming `go test ./...` will pass).

When writing Go, follow the naming conventions in `.agents/rules/named.md` (package/file/interface/error naming — e.g. `ErrNotFound`, `-er` interfaces, no `util` packages).

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
- `test/testcases/test_http_api/` and `test/testcases/test_sdk_api/` — integration tests that hit a running RAGFlow stack via HTTP or the Python SDK. They expect `HOST_ADDRESS` (default `http://127.0.0.1:9380`) and accept a custom `--level` flag (`p0`/`p1`/`p2`/`p3`) to filter by priority marker.
- `test/playwright/` — Playwright UI tests.

Useful invocations:

```bash
uv run pytest                                         # all unit tests
uv run pytest test/unit_test/<path>.py::TestX::test_y # single test
uv run pytest -m p1                                   # priority filter (markers: p0/p1/p2/p3, smoke, auth, asyncio)
pytest -s --tb=short --level=p2 test/testcases/test_http_api    # integration vs running stack
DOC_ENGINE=infinity pytest --level=p2 test/testcases/test_sdk_api  # against Infinity
```

`pyproject.toml` sets `filterwarnings = ["error", ...]` — warnings are errors by default. Markers are strict (`--strict-markers`); register new ones in `pyproject.toml` before using.

### Lint / format (Python)

`ruff` is configured with `line-length = 200` and extra-selects `ASYNC`/`ASYNC1` (so misuse of async/await is caught). `rag/svr/discord_svr.py` is excluded.

```bash
ruff check
ruff format
```

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
- `go.mod` — note the `replace` directive pinning `infinity-go-sdk` to a specific commit of `infiniflow/infinity/go`.

## Repo-root scratch files

The repo root contains a number of ad-hoc scripts and JSON dumps from past investigations (e.g. `test_50_questions.py`, `dump_all_chunks.py`, `req_*.json`, `resp_*.json`, `test_report*.txt`). These are **not** part of the package or test suite (`pyproject.toml`'s `testpaths = ["test"]` excludes them). Treat them as throwaway unless a specific task references one — don't lint, refactor, or "clean them up" proactively.

**Exception — keep these repo-root docs:** `SERVICE_CONTRACT.md` (plus `SERVICE_CONTRACT_BRIEF.md` / `_CONTINUE.md`) and `EXTERNAL_API_GUIDE.md` are deliberate, **live-verified** references for the running v0.25.0 Docker stack, not scratch. `SERVICE_CONTRACT.md` is the authoritative API contract — trust it over the official RAGFlow docs where they conflict (e.g. `/chats` response fields, markdown `VISION`, cross-language retrieval). `EXTERNAL_API_GUIDE.md` (Hebrew) is an integration guide for calling the local stack at `http://localhost:9380/api/v1` from an external project. When working against the live API, consult these before assuming endpoint behavior.
