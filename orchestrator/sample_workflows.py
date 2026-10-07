from __future__ import annotations

from typing import Any

from orchestrator.engine import ExecutionPolicy, WorkflowEngine, retry_policy
from orchestrator.models import NodeResult, NodeStatus, Stage, WorkflowNode, WorkflowReport


def run_greenfield_scenario() -> WorkflowReport:
    context: dict[str, Any] = {
        "approved_release": True,
        "security_scan_passed": True,
        "compliance_check_passed": True,
    }
    nodes = [
        WorkflowNode(
            node_id="req",
            stage=Stage.REQUIREMENTS,
            title="Normalize requirements into REQ items",
            deps=[],
            produces={"requirements"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"req_count": 8}),
        ),
        WorkflowNode(
            node_id="arch",
            stage=Stage.ARCHITECTURE,
            title="Generate architecture and ADRs",
            deps=["req"],
            consumes={"requirements"},
            produces={"architecture"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"adrs": 3}),
        ),
        WorkflowNode(
            node_id="impl",
            stage=Stage.IMPLEMENTATION,
            title="Generate implementation outputs",
            deps=["arch"],
            consumes={"architecture"},
            produces={"code"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"files_changed": 12}),
        ),
        WorkflowNode(
            node_id="test",
            stage=Stage.TESTING,
            title="Run integration and unit tests",
            deps=["impl"],
            consumes={"code"},
            produces={"test_results"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"pass_rate": 1.0}),
        ),
        WorkflowNode(
            node_id="docs",
            stage=Stage.DOCUMENTATION,
            title="Generate release docs",
            deps=["impl"],
            consumes={"code"},
            produces={"documentation"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"pages": 5}),
        ),
        WorkflowNode(
            node_id="release",
            stage=Stage.RELEASE,
            title="Release readiness gate",
            deps=["test", "docs"],
            consumes={"test_results", "documentation"},
            requires_approval=True,
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"ready": True}),
        ),
    ]
    engine = WorkflowEngine("greenfield", nodes)
    return engine.execute(context=context)


def run_brownfield_scenario() -> WorkflowReport:
    state: dict[str, int] = {"impl_runs": 0}

    def implement(ctx: dict[str, Any]) -> NodeResult:
        state["impl_runs"] += 1
        if state["impl_runs"] == 1:
            raise RuntimeError("Refactor introduced regression in redirect handler.")
        return NodeResult(NodeStatus.SUCCEEDED, {"refactor_status": "stable"})

    context: dict[str, Any] = {
        "approved_release": True,
        "security_scan_passed": True,
        "compliance_check_passed": True,
    }
    nodes = [
        WorkflowNode(
            node_id="impact",
            stage=Stage.REQUIREMENTS,
            title="Analyze impacted modules",
            deps=[],
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"modules": ["service", "api"]}),
            produces={"impact_map"},
        ),
        WorkflowNode(
            node_id="impl_refactor",
            stage=Stage.IMPLEMENTATION,
            title="Execute refactor with bounded retries",
            deps=["impact"],
            consumes={"impact_map"},
            produces={"code"},
            run=implement,
            retry_policy=retry_policy(max_attempts=2, backoff_seconds=0.01),
            rollback=lambda ctx: ctx.update({"rollback_executed": True}),
            fallback=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"fallback_path": "safe_patch"}),
        ),
        WorkflowNode(
            node_id="test_refactor",
            stage=Stage.TESTING,
            title="Regression and compatibility tests",
            deps=["impl_refactor"],
            consumes={"code"},
            produces={"test_results"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"tests_passed": 42}),
        ),
        WorkflowNode(
            node_id="release_refactor",
            stage=Stage.RELEASE,
            title="Change-control approval",
            deps=["test_refactor"],
            requires_approval=True,
            consumes={"test_results"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"approved": True}),
        ),
    ]
    engine = WorkflowEngine("brownfield", nodes)
    return engine.execute(context=context)


def run_ambiguous_scenario() -> WorkflowReport:
    context: dict[str, Any] = {
        "approved_release": True,
        "security_scan_passed": True,
        "compliance_check_passed": True,
        "requirements_revision": 0,
    }

    def clarify_requirements(ctx: dict[str, Any]) -> NodeResult:
        if ctx["requirements_revision"] == 0:
            ctx["requirements_revision"] = 1
            return NodeResult(
                status=NodeStatus.SUCCEEDED,
                output={"clarified": True},
                requires_replan=True,
            )
        return NodeResult(status=NodeStatus.SUCCEEDED, output={"clarified": True})

    nodes = [
        WorkflowNode(
            node_id="capture",
            stage=Stage.REQUIREMENTS,
            title="Capture initial intent",
            deps=[],
            produces={"raw_requirements"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"raw": "support custom aliases"}),
        ),
        WorkflowNode(
            node_id="clarify",
            stage=Stage.REQUIREMENTS,
            title="Human clarification checkpoint",
            deps=["capture"],
            consumes={"raw_requirements"},
            produces={"requirements"},
            run=clarify_requirements,
            requires_approval=True,
        ),
        WorkflowNode(
            node_id="design",
            stage=Stage.ARCHITECTURE,
            title="Revise architecture from clarified requirements",
            deps=["clarify"],
            consumes={"requirements"},
            produces={"architecture"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"diagram_version": ctx["requirements_revision"]}),
        ),
        WorkflowNode(
            node_id="implement",
            stage=Stage.IMPLEMENTATION,
            title="Implement revised stories",
            deps=["design"],
            consumes={"architecture"},
            produces={"code"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"features": ["alias", "ttl"]}),
        ),
        WorkflowNode(
            node_id="validate",
            stage=Stage.TESTING,
            title="Validate acceptance criteria",
            deps=["implement"],
            consumes={"code"},
            produces={"test_results"},
            run=lambda ctx: NodeResult(NodeStatus.SUCCEEDED, {"acceptance_passed": True}),
        ),
    ]
    policy = ExecutionPolicy(
        approval_callback=lambda node, ctx: True,
        guardrails=[],
        max_parallelism=2,
    )
    engine = WorkflowEngine("ambiguous", nodes, policy=policy)
    return engine.execute(context=context)

