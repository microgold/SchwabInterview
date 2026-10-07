from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class Stage(str, Enum):
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    RELEASE = "release"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass(frozen=True)
class NodeResult:
    status: NodeStatus
    output: dict[str, Any] = field(default_factory=dict)
    warning: str | None = None
    requires_replan: bool = False


@dataclass
class WorkflowNode:
    node_id: str
    stage: Stage
    title: str
    deps: list[str]
    run: Callable[[dict[str, Any]], NodeResult]
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    requires_approval: bool = False
    rollback: Callable[[dict[str, Any]], None] | None = None
    fallback: Callable[[dict[str, Any]], NodeResult] | None = None
    produces: set[str] = field(default_factory=set)
    consumes: set[str] = field(default_factory=set)
    status: NodeStatus = NodeStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    observed_versions: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEvent:
    timestamp: datetime
    node_id: str
    action: str
    detail: str

    @staticmethod
    def make(node_id: str, action: str, detail: str) -> "WorkflowEvent":
        return WorkflowEvent(
            timestamp=datetime.now(timezone.utc),
            node_id=node_id,
            action=action,
            detail=detail,
        )


@dataclass(frozen=True)
class WorkflowMetrics:
    total_nodes: int
    succeeded_nodes: int
    failed_nodes: int
    rolled_back_nodes: int
    retried_nodes: int
    success_rate: float
    mttr_seconds: float
    end_to_end_latency_seconds: float


@dataclass(frozen=True)
class WorkflowReport:
    workflow_name: str
    status: NodeStatus
    context: dict[str, Any]
    events: list[WorkflowEvent]
    metrics: WorkflowMetrics
