from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from orchestrator.models import (
    NodeResult,
    NodeStatus,
    RetryPolicy,
    WorkflowEvent,
    WorkflowMetrics,
    WorkflowNode,
    WorkflowReport,
)

ApprovalCallback = Callable[[WorkflowNode, dict[str, object]], bool]
GuardrailCallback = Callable[[WorkflowNode, dict[str, object]], tuple[bool, str]]


@dataclass
class ExecutionPolicy:
    approval_callback: ApprovalCallback
    guardrails: list[GuardrailCallback]
    max_parallelism: int = 4


def allow_all_approval(node: WorkflowNode, context: dict[str, object]) -> bool:
    _ = context
    return not node.requires_approval or context.get("approved_release", False) is True


def release_guardrail(node: WorkflowNode, context: dict[str, object]) -> tuple[bool, str]:
    if node.stage.value != "release":
        return True, ""
    if context.get("security_scan_passed") is not True:
        return False, "Security gate not satisfied."
    if context.get("compliance_check_passed") is not True:
        return False, "Compliance gate not satisfied."
    return True, ""


class WorkflowEngine:
    def __init__(
        self,
        workflow_name: str,
        nodes: list[WorkflowNode],
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self._workflow_name = workflow_name
        self._nodes = {node.node_id: node for node in nodes}
        self._dependents = self._build_dependents(nodes)
        self._events: list[WorkflowEvent] = []
        self._artifact_versions: dict[str, int] = {}
        self._failed_timestamps: list[datetime] = []
        self._recovered_timestamps: list[datetime] = []
        self._rolled_back_nodes = 0
        self._retried_nodes = 0
        self._stop_requested = False
        self._lock = Lock()
        self._policy = policy or ExecutionPolicy(
            approval_callback=allow_all_approval,
            guardrails=[release_guardrail],
        )

    def request_safe_stop(self, reason: str) -> None:
        with self._lock:
            self._stop_requested = True
            self._events.append(WorkflowEvent.make("workflow", "safe_stop_requested", reason))

    def execute(self, context: dict[str, object] | None = None) -> WorkflowReport:
        run_context: dict[str, object] = dict(context or {})
        start = datetime.now(timezone.utc)
        self._events.append(WorkflowEvent.make("workflow", "start", "Workflow execution started."))

        while True:
            if self._stop_requested:
                self._events.append(
                    WorkflowEvent.make("workflow", "stopped", "Workflow stopped by safe-stop signal.")
                )
                return self._build_report(NodeStatus.BLOCKED, run_context, start)

            ready_nodes = self._get_ready_nodes()
            if not ready_nodes:
                break

            with ThreadPoolExecutor(max_workers=self._policy.max_parallelism) as executor:
                futures = {executor.submit(self._execute_node, node, run_context): node for node in ready_nodes}
                for future in as_completed(futures):
                    node = futures[future]
                    result = future.result()
                    self._handle_result(node=node, result=result, context=run_context)
                    if result.status == NodeStatus.FAILED:
                        self._events.append(
                            WorkflowEvent.make("workflow", "failed", f"Node {node.node_id} failed terminally.")
                        )
                        return self._build_report(NodeStatus.FAILED, run_context, start)

        final_status = NodeStatus.SUCCEEDED if all(
            node.status == NodeStatus.SUCCEEDED for node in self._nodes.values()
        ) else NodeStatus.BLOCKED
        return self._build_report(final_status, run_context, start)

    def _execute_node(self, node: WorkflowNode, context: dict[str, object]) -> NodeResult:
        node.status = NodeStatus.RUNNING
        self._events.append(WorkflowEvent.make(node.node_id, "running", node.title))

        if node.requires_approval and not self._policy.approval_callback(node, context):
            node.status = NodeStatus.BLOCKED
            return NodeResult(status=NodeStatus.FAILED, warning="Approval checkpoint denied.")

        for guardrail in self._policy.guardrails:
            allowed, reason = guardrail(node, context)
            if not allowed:
                node.status = NodeStatus.BLOCKED
                return NodeResult(status=NodeStatus.FAILED, warning=reason)

        attempts = max(1, node.retry_policy.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                node.attempts += 1
                if attempt > 1:
                    self._retried_nodes += 1
                    self._events.append(
                        WorkflowEvent.make(node.node_id, "retry", f"Retry attempt {attempt}/{attempts}.")
                    )
                result = node.run(context)
                return result
            except Exception as exc:  # noqa: BLE001
                node.last_error = str(exc)
                if attempt >= attempts:
                    self._failed_timestamps.append(datetime.now(timezone.utc))
                    if node.fallback:
                        self._events.append(
                            WorkflowEvent.make(node.node_id, "fallback", "Executing fallback after failure.")
                        )
                        try:
                            return node.fallback(context)
                        except Exception as fallback_exc:  # noqa: BLE001
                            node.last_error = f"{exc}; fallback failed: {fallback_exc}"
                            return NodeResult(status=NodeStatus.FAILED, warning=node.last_error)
                    return NodeResult(status=NodeStatus.FAILED, warning=node.last_error)
                if node.retry_policy.backoff_seconds > 0:
                    time.sleep(node.retry_policy.backoff_seconds * attempt)

        return NodeResult(status=NodeStatus.FAILED, warning="Unknown execution failure.")

    def _handle_result(self, node: WorkflowNode, result: NodeResult, context: dict[str, object]) -> None:
        context[node.node_id] = result.output
        if result.status == NodeStatus.SUCCEEDED:
            node.status = NodeStatus.SUCCEEDED
            node.observed_versions = {artifact: self._artifact_versions.get(artifact, 0) for artifact in node.consumes}
            for artifact in node.produces:
                self._artifact_versions[artifact] = self._artifact_versions.get(artifact, 0) + 1
            self._events.append(WorkflowEvent.make(node.node_id, "succeeded", node.title))
            self._mark_stale_dependents(node)
            if self._failed_timestamps:
                self._recovered_timestamps.append(datetime.now(timezone.utc))
        elif result.status == NodeStatus.SKIPPED:
            node.status = NodeStatus.SKIPPED
            self._events.append(WorkflowEvent.make(node.node_id, "skipped", result.warning or node.title))
        else:
            node.status = NodeStatus.FAILED
            self._events.append(
                WorkflowEvent.make(node.node_id, "failed", result.warning or node.last_error or node.title)
            )
            if node.rollback:
                try:
                    node.rollback(context)
                    self._rolled_back_nodes += 1
                    self._events.append(WorkflowEvent.make(node.node_id, "rollback", "Rollback completed."))
                except Exception as rollback_exc:  # noqa: BLE001
                    self._events.append(
                        WorkflowEvent.make(node.node_id, "rollback_failed", f"Rollback failed: {rollback_exc}")
                    )

    def _mark_stale_dependents(self, changed_node: WorkflowNode) -> None:
        queue = list(self._dependents.get(changed_node.node_id, []))
        while queue:
            dependent_id = queue.pop(0)
            dependent = self._nodes[dependent_id]
            if dependent.status == NodeStatus.SUCCEEDED:
                stale = any(
                    dependent.observed_versions.get(artifact, 0) < self._artifact_versions.get(artifact, 0)
                    for artifact in dependent.consumes
                )
                if stale:
                    dependent.status = NodeStatus.PENDING
                    self._events.append(
                        WorkflowEvent.make(dependent.node_id, "replan", "Upstream output changed; node re-queued.")
                    )
                    queue.extend(self._dependents.get(dependent_id, []))

    def _get_ready_nodes(self) -> list[WorkflowNode]:
        ready: list[WorkflowNode] = []
        for node in self._nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            if all(self._nodes[dep].status == NodeStatus.SUCCEEDED for dep in node.deps):
                ready.append(node)
        return ready

    def _build_dependents(self, nodes: list[WorkflowNode]) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {node.node_id: [] for node in nodes}
        for node in nodes:
            for dep in node.deps:
                graph[dep].append(node.node_id)
        return graph

    def _build_report(
        self,
        status: NodeStatus,
        context: dict[str, object],
        start: datetime,
    ) -> WorkflowReport:
        end = datetime.now(timezone.utc)
        succeeded_nodes = sum(1 for node in self._nodes.values() if node.status == NodeStatus.SUCCEEDED)
        failed_nodes = sum(1 for node in self._nodes.values() if node.status == NodeStatus.FAILED)
        total_nodes = len(self._nodes)
        success_rate = succeeded_nodes / total_nodes if total_nodes else 0.0
        mttr = self._calculate_mttr_seconds()
        metrics = WorkflowMetrics(
            total_nodes=total_nodes,
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            rolled_back_nodes=self._rolled_back_nodes,
            retried_nodes=self._retried_nodes,
            success_rate=success_rate,
            mttr_seconds=mttr,
            end_to_end_latency_seconds=(end - start).total_seconds(),
        )
        self._events.append(WorkflowEvent.make("workflow", "complete", f"Status: {status.value}"))
        return WorkflowReport(
            workflow_name=self._workflow_name,
            status=status,
            context=context,
            events=list(self._events),
            metrics=metrics,
        )

    def _calculate_mttr_seconds(self) -> float:
        pairs = min(len(self._failed_timestamps), len(self._recovered_timestamps))
        if pairs == 0:
            return 0.0
        durations = [
            (self._recovered_timestamps[idx] - self._failed_timestamps[idx]).total_seconds()
            for idx in range(pairs)
        ]
        return sum(durations) / len(durations)


def retry_policy(max_attempts: int, backoff_seconds: float) -> RetryPolicy:
    return RetryPolicy(max_attempts=max_attempts, backoff_seconds=backoff_seconds)
