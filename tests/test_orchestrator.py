from __future__ import annotations

from orchestrator.models import NodeStatus
from orchestrator.sample_workflows import (
    run_ambiguous_scenario,
    run_brownfield_scenario,
    run_greenfield_scenario,
)


def test_greenfield_workflow_succeeds() -> None:
    report = run_greenfield_scenario()
    assert report.status == NodeStatus.SUCCEEDED
    assert report.metrics.success_rate == 1.0
    assert report.metrics.failed_nodes == 0


def test_brownfield_workflow_uses_retry_and_fallback() -> None:
    report = run_brownfield_scenario()
    assert report.status == NodeStatus.SUCCEEDED
    assert report.metrics.retried_nodes >= 1
    assert report.context["impl_refactor"]["refactor_status"] == "stable"


def test_ambiguous_workflow_succeeds_with_replanning_context() -> None:
    report = run_ambiguous_scenario()
    assert report.status == NodeStatus.SUCCEEDED
    assert report.context["design"]["diagram_version"] == 1

