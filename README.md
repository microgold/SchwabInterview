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

Protected API endpoints require an API key:

- Header: `X-API-Key: <key>` (or `Authorization: Bearer <key>`)
- Default key: `dev-interview-key`
- Configure with `SHORTENER_API_KEY`

### 3) Run tests

```powershell
pytest -q
```

### 4) Run orchestration demo scenarios

```powershell
python scripts\run_workflow_demo.py
```

This generates [workflow_demo_report.json](C:/Repos/SchwabInterview/data/workflow_demo_report.json).

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
