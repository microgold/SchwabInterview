# Final Engineering Summary

## Plan and Rationale

I used Python + FastAPI for rapid delivery of a production-shaped API with explicit types, validation, and easy testability.

Primary design choices:

1. **Simple and reliable storage**: SQLite for local portability and deterministic tests.
2. **Layered design**: API → Service → Repository for maintainability and clear boundaries.
3. **Controlled autonomy orchestration**: explicit DAG nodes with approvals, retries, rollbacks, fallback, and guardrails.
4. **Evidence-driven quality**: unit/integration tests + scenario workflows + metrics output.

## Delivered Artifacts

- Runnable API: [app/main.py](C:/Repos/SchwabInterview/app/main.py)
- Domain logic: [app/service.py](C:/Repos/SchwabInterview/app/service.py)
- Persistence: [app/repository.py](C:/Repos/SchwabInterview/app/repository.py)
- Agentic orchestration core: [orchestrator/engine.py](C:/Repos/SchwabInterview/orchestrator/engine.py)
- Required scenarios: [orchestrator/sample_workflows.py](C:/Repos/SchwabInterview/orchestrator/sample_workflows.py)
- Scenario runner: [run_workflow_demo.py](C:/Repos/SchwabInterview/scripts/run_workflow_demo.py)
- Tests: [tests/](C:/Repos/SchwabInterview/tests)
- Setup guide: [README.md](C:/Repos/SchwabInterview/README.md)
- Architecture/scenario docs: [docs/](C:/Repos/SchwabInterview/docs)

## Validation Strategy and Guardrails

1. **Functional validation**
   - endpoint behavior (create, redirect, analytics)
   - conflict handling for custom aliases
2. **Reliability validation**
   - retry/fallback behavior in brownfield scenario
   - guarded release stage for security/compliance
3. **Governance**
   - human approval checkpoint on release/high-impact actions
   - safe-stop control for operational interruption
4. **Traceability**
   - workflow event logs and metrics report artifacts

## Risks, Trade-offs, and Limitations

1. SQLite is ideal for a prototype but not horizontally scalable; production would use managed DB + cache.
2. Visitor uniqueness is approximated by `hash(client_host + user_agent)` and can over/under-count in shared-network contexts.
3. Orchestration is intentionally in-process for clarity; production should externalize state (durable queue/workflow engine).
4. Security controls are represented as policy gates and flags; enterprise integration should connect to actual scanners and approval systems.

## Assumptions

1. Internal prototype does not require authentication/authorization for API endpoints.
2. A single deployment base URL is acceptable for generated short links.
3. Human approval is represented through callback/policy state rather than interactive UI workflow.

