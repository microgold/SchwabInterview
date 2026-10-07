# Agentic URL Shortener (Interview Prototype)

This repository contains a runnable **URL shortener service** and an **agentic SDLC orchestration layer** designed to satisfy the assignment requirements:

- requirement normalization and decomposition
- controlled autonomous execution
- policy guardrails and human approvals
- retry/fallback/rollback/safe-stop controls
- audit and reliability metrics

## Quick Start

### Simplified start scripts

From the repository root, start the server:

```powershell
.\scripts\run_api.ps1
```

Then open the simple UI:

```powershell
Start-Process "http://127.0.0.1:8000/ui"
```

Open the interactive Swagger API documentation:

```powershell
Start-Process "http://127.0.0.1:8000/docs"
```

Press `Ctrl+C` in the server terminal to stop it.

### 1) Create environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Run the URL shortener API

```powershell
uvicorn app.main:app --reload
```

Service runs at `http://localhost:8000`.
Interactive UI is available at `http://localhost:8000/ui`.
Swagger API documentation is available at `http://localhost:8000/docs`.

Protected API endpoints require an API key. For local interview and demo use, the default key is:

```text
dev-interview-key
```

Send it with either supported authorization header:

- Header: `X-API-Key: <key>` (or `Authorization: Bearer <key>`)
- Example: `X-API-Key: dev-interview-key`

> **Interview/demo use only:** Replace the default by setting `SHORTENER_API_KEY` before deploying the application. Do not use the default key in production.

### 3) Run tests

```powershell
pytest -q
```

### 4) Run orchestration demo scenarios

```powershell
python scripts\run_workflow_demo.py
```

This generates [workflow_demo_report.json](C:/Repos/SchwabInterview/data/workflow_demo_report.json).

The three demo scenarios are deterministic simulations used to exercise graph scheduling, retries,
fallbacks, approvals, and metrics. To run the orchestration layer against the real repository, use
the bounded Codex-backed workflow below.

### 5) Run a real agentic SDLC workflow

Prerequisites:

```powershell
codex --version
codex login status
```

> **Data boundary:** Running this workflow sends the requirement and relevant repository context to
> Codex under the account shown by `codex login status`. Review the repository for secrets or
> confidential material and confirm that this transmission is permitted before continuing.

Provide a concrete requirement and explicitly allow only the files or directories the implementation
agent may change:

```powershell
python scripts\run_agentic_sdlc.py `
  --requirement "Describe one small URL-shortener change and its expected behavior" `
  --allow app `
  --allow tests `
  --allow docs
```

The workflow:

1. Uses Codex in read-only mode to normalize the requirement and inspect its code impact.
2. Requests approval before implementation.
3. Copies the repository to an isolated temporary workspace.
4. Lets Codex edit only the staged copy and rejects changes outside the allowlist.
5. Runs the real `pytest` suite and Python compilation checks.
6. Uses a separate read-only Codex pass to review the changed files and validation evidence.
7. Requests final approval before copying validated files back to the repository.
8. Writes prompts, structured agent outputs, command evidence, events, and metrics under
   `data/agent_runs/<run-id>/`.

Use `--requirement-file <path>` for a longer requirement. The optional `--approve-plan` and
`--approve-release` flags support trusted non-interactive demonstrations; omit them to retain both
interactive human checkpoints. The workflow prepares a reviewable local change but does not commit,
push, or deploy it.

### Easy scripts (recommended)

From [scripts/](C:/Repos/SchwabInterview/scripts):

1. Setup environment:
```powershell
.\scripts\setup_env.ps1
```

2. Run API (with auth key):
```powershell
.\scripts\run_api.ps1 -ApiKey "dev-interview-key"
```

3. Smoke test a running API:
```powershell
.\scripts\smoke_test.ps1 -BaseUrl "http://127.0.0.1:8000" -ApiKey "dev-interview-key"
```

4. One-command full verification (tests + workflow demo + smoke test):
```powershell
.\scripts\verify_all.ps1
```

---

## API Endpoints

- `POST /api/v1/shorten` create shortened URL (supports custom alias and TTL)
- `GET /{short_code}` redirect and track click analytics
- `GET /api/v1/urls/{short_code}` retrieve URL metadata
- `GET /api/v1/analytics/{short_code}` retrieve analytics (click count, unique visitors, last access)
- `GET /health` service health
- `GET /ui` minimal interactive test UI

---

## Project Structure

- API and domain logic: [app/](C:/Repos/SchwabInterview/app)
  - [main.py](C:/Repos/SchwabInterview/app/main.py)
  - [service.py](C:/Repos/SchwabInterview/app/service.py)
  - [repository.py](C:/Repos/SchwabInterview/app/repository.py)
- Agentic orchestration engine: [orchestrator/](C:/Repos/SchwabInterview/orchestrator)
  - [engine.py](C:/Repos/SchwabInterview/orchestrator/engine.py)
  - [sample_workflows.py](C:/Repos/SchwabInterview/orchestrator/sample_workflows.py)
- Tests: [tests/](C:/Repos/SchwabInterview/tests)
- Assignment-focused docs: [docs/](C:/Repos/SchwabInterview/docs)

---

## Notes

- Default DB is SQLite at `data/shortener.db` (configurable via `SHORTENER_DB_PATH`).
- In-memory rate limiting is enabled:
  - API endpoints: `SHORTENER_API_RATE_LIMIT_PER_MINUTE` (default `120`)
  - Redirect endpoint: `SHORTENER_REDIRECT_RATE_LIMIT_PER_MINUTE` (default `240`)
- The orchestrator demonstrates governance and reliability controls over SDLC stages.
- For assignment narrative and trade-offs, see [engineering_summary.md](C:/Repos/SchwabInterview/docs/engineering_summary.md).
