# Required Scenarios

## Greenfield Scenario

- **Goal**: Build URL shortener capabilities from scratch.
- **Workflow**: requirements → architecture → implementation → (testing + docs in parallel) → release approval.
- **Validation**:
  - API tests pass
  - release gate requires security/compliance flags plus human approval
- **Implementation**: [run_greenfield_scenario](C:/Repos/SchwabInterview/orchestrator/sample_workflows.py:12)

## Brownfield Scenario

- **Goal**: Enhance/refactor existing URL redirection logic while minimizing regression risk.
- **Workflow features demonstrated**:
  - impact analysis on modules
  - retry on refactor failure
  - fallback strategy
  - rollback hook support
  - release change-control checkpoint
- **Implementation**: [run_brownfield_scenario](C:/Repos/SchwabInterview/orchestrator/sample_workflows.py:72)

## Ambiguous Requirement Scenario

- **Ambiguity**: requirement intent changes after initial capture.
- **Workflow features demonstrated**:
  - human clarification checkpoint
  - upstream change propagation
  - dynamic downstream re-queue/re-plan behavior through artifact versions
- **Implementation**: [run_ambiguous_scenario](C:/Repos/SchwabInterview/orchestrator/sample_workflows.py:123)

