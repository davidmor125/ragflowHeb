# RAGFlow workspace instructions for GitHub Copilot

These instructions help AI agents work in the RAGFlow repository. For deeper architecture and full project context, also consult `AGENTS.md` at the repo root.

## How to run

### Backend
- Create and activate the Python virtual environment:
  - `python -m venv .venv && .venv\Scripts\activate` on Windows
  - `python -m venv .venv && source .venv/bin/activate` on Linux/macOS
- Install dependencies:
  - `pip install -r requirements.txt`
- Run backend services and app:
  - `docker compose -f docker/docker-compose-base.yml up -d`
  - `bash docker/launch_backend_service.sh`
- Use `uv` when available for dependency and test commands.

### Frontend
- Change into the frontend folder:
  - `cd web`
- Install dependencies:
  - `npm install`
- Start the dev server:
  - `npm run dev`

## How to test
- Backend tests:
  - `uv run pytest`
  - `uv run pytest test/test_api.py`
- Frontend tests:
  - `cd web && npm run test`
- Linting and formatting:
  - `ruff check`
  - `ruff format`
  - `cd web && npm run lint`

## Key directories
- `api/`: backend server and API blueprints
- `rag/`: core retrieval and embedding pipeline
- `deepdoc/`: document parsing, OCR, and layout analysis
- `agent/`: agent workflows and tools
- `web/`: frontend React/Umi app
- `docker/`: compose files and deployment scripts
- `test/`: backend tests

## Code conventions
- Prefer small, incremental changes.
- Add or update tests for behavior changes.
- Add logging for new backend flows.
- Keep backend code Pythonic and follow existing project patterns.
- For frontend work, follow React/TypeScript and existing `web/` conventions.

## Notes for agents
- When asked to modify backend behavior, prefer file changes in `api/`, `rag/`, or `agent/`.
- When asked to modify UI behavior, focus on `web/` and existing frontend patterns.
- If a task touches build or runtime configuration, verify the command with `AGENTS.md` and the repository README.
