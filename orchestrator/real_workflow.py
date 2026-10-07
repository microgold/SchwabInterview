from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable

from orchestrator.engine import ExecutionPolicy, WorkflowEngine, retry_policy
from orchestrator.models import NodeResult, NodeStatus, Stage, WorkflowNode, WorkflowReport


PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "normalized_requirement": {"type": "string"},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {"type": "string"}},
        "impacted_paths": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "normalized_requirement",
        "ambiguities",
        "acceptance_criteria",
        "tasks",
        "impacted_paths",
        "risks",
    ],
    "additionalProperties": False,
}

DESIGN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "design_summary": {"type": "string"},
        "data_flow": {"type": "array", "items": {"type": "string"}},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "validation_plan": {"type": "array", "items": {"type": "string"}},
        "files_expected_to_change": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "design_summary",
        "data_flow",
        "decisions",
        "validation_plan",
        "files_expected_to_change",
    ],
    "additionalProperties": False,
}

IMPLEMENTATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "tests_added_or_updated": {"type": "array", "items": {"type": "string"}},
        "known_limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "files_changed", "tests_added_or_updated", "known_limitations"],
    "additionalProperties": False,
}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "changes_requested"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "path": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["severity", "path", "description"],
                "additionalProperties": False,
            },
        },
        "requirement_coverage": {"type": "array", "items": {"type": "string"}},
        "residual_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "findings", "requirement_coverage", "residual_risks"],
    "additionalProperties": False,
}


class CodexCliAgent:
    """Runs bounded Codex CLI tasks and stores an audit trail for every invocation."""

    def __init__(self, audit_root: Path, timeout_seconds: int = 900) -> None:
        self.audit_root = audit_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.executable = shutil.which("codex")
        if not self.executable:
            raise RuntimeError("Codex CLI was not found on PATH. Install it and run `codex login`.")

    def run_json(
        self,
        *,
        stage: str,
        prompt: str,
        schema: dict[str, Any],
        workspace: Path,
        writable: bool,
    ) -> dict[str, Any]:
        stage_dir = self.audit_root / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = stage_dir / "prompt.txt"
        schema_path = stage_dir / "schema.json"
        answer_path = stage_dir / "answer.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

        args = [
            self.executable,
            "exec",
            "--ephemeral",
            "--color",
            "never",
            "--sandbox",
            "workspace-write" if writable else "read-only",
            "--skip-git-repo-check",
            "--cd",
            str(workspace.resolve()),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(answer_path),
            "-",
        ]
        if os.name == "nt" and Path(self.executable).suffix.lower() in {".cmd", ".bat"}:
            command = ["cmd.exe", "/d", "/s", "/c", subprocess.list2cmdline(args)]
        else:
            command = args

        try:
            result = subprocess.run(
                command,
                input=prompt,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Codex stage {stage!r} timed out after {exc.timeout} seconds.") from exc

        (stage_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (stage_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(
                f"Codex stage {stage!r} exited with {result.returncode}; see {stage_dir / 'stderr.txt'}."
            )
        if not answer_path.exists():
            raise RuntimeError(f"Codex stage {stage!r} did not produce {answer_path}.")
        return json.loads(answer_path.read_text(encoding="utf-8"))


def _ignore_staging(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".codex",
        ".agents",
        "agent_runs",
    }
    return {name for name in names if name in ignored or name.endswith((".pyc", ".pyo"))}


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in {".git", ".venv", "venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _is_allowed(relative_path: str, allowed_paths: tuple[str, ...]) -> bool:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    return any(
        normalized == allowed.rstrip("/") or normalized.startswith(f"{allowed.rstrip('/')}/")
        for allowed in allowed_paths
    )


def _changed_paths(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str]]:
    changed = sorted(path for path in after if before.get(path) != after[path])
    deleted = sorted(path for path in before if path not in after)
    return changed, deleted


def _short_output(value: str, limit: int = 4000) -> str:
    return value if len(value) <= limit else value[-limit:]


def _prompt_for_approval(message: str) -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_real_agentic_workflow(
    *,
    repository: Path,
    requirement: str,
    allowed_paths: list[str],
    approve_plan: bool = False,
    approve_release: bool = False,
    approval_callback: Callable[[str], bool] | None = None,
    agent: CodexCliAgent | None = None,
) -> WorkflowReport:
    """Run an evidence-backed SDLC workflow and promote only approved, allowlisted changes."""

    repo = repository.resolve()
    if not requirement.strip():
        raise ValueError("A non-empty requirement is required.")
    normalized_allowed = tuple(path.replace("\\", "/").strip("/") for path in allowed_paths if path.strip("/"))
    if not normalized_allowed:
        raise ValueError("At least one allowed path is required.")
    if any(path.startswith("..") or Path(path).is_absolute() for path in normalized_allowed):
        raise ValueError("Allowed paths must be relative paths inside the repository.")

    run_id = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    audit_root = repo / "data" / "agent_runs" / run_id
    staging = Path(tempfile.mkdtemp(prefix=f"agentic-sdlc-{run_id}-"))
    audit_root.mkdir(parents=True, exist_ok=False)
    active_agent = agent or CodexCliAgent(audit_root / "agent_calls")
    approve = approval_callback or _prompt_for_approval
    context: dict[str, Any] = {
        "requirement": requirement.strip(),
        "allowed_paths": list(normalized_allowed),
        "approved_plan": approve_plan,
        "approved_release": approve_release,
        "security_scan_passed": True,
        "compliance_check_passed": True,
        "audit_directory": str(audit_root),
        "staging_directory": str(staging),
    }

    def requirements_action(ctx: dict[str, Any]) -> NodeResult:
        prompt = (
            "Act as the requirements agent for this repository. Inspect the repository in read-only mode. "
            "Normalize the requirement, identify genuine ambiguities, write testable acceptance criteria, "
            "decompose the work, and identify impacted paths. Do not edit files. "
            f"Requirement: {ctx['requirement']}\n"
            f"Permitted implementation paths: {json.dumps(ctx['allowed_paths'])}"
        )
        output = active_agent.run_json(
            stage="01_requirements", prompt=prompt, schema=PLAN_SCHEMA, workspace=repo, writable=False
        )
        return NodeResult(NodeStatus.SUCCEEDED, output)

    def architecture_action(ctx: dict[str, Any]) -> NodeResult:
        plan = ctx["requirements"]
        prompt = (
            "Act as the architecture and brownfield impact-analysis agent. Inspect the repository in read-only "
            "mode. Produce the smallest maintainable design, expected data flow, key decisions, concrete validation "
            "plan, and files expected to change. Do not edit files and do not expand beyond the permitted paths.\n"
            f"Requirement: {ctx['requirement']}\nPlan: {json.dumps(plan, indent=2)}\n"
            f"Permitted paths: {json.dumps(ctx['allowed_paths'])}"
        )
        output = active_agent.run_json(
            stage="02_architecture", prompt=prompt, schema=DESIGN_SCHEMA, workspace=repo, writable=False
        )
        return NodeResult(NodeStatus.SUCCEEDED, output)

    def implementation_action(ctx: dict[str, Any]) -> NodeResult:
        shutil.copytree(repo, staging, ignore=_ignore_staging, dirs_exist_ok=True)
        before = _file_hashes(staging)
        ctx["staging_before"] = before
        prompt = (
            "Act as the implementation agent. Implement the approved requirement in this isolated staging copy. "
            "Make the smallest useful production-quality change and add or update tests. You may edit only the "
            "permitted paths. Do not delete files, modify generated audit data, commit, push, deploy, or claim tests "
            "passed. Validation runs separately after you finish.\n"
            f"Requirement: {ctx['requirement']}\n"
            f"Approved plan: {json.dumps(ctx['requirements'], indent=2)}\n"
            f"Approved design: {json.dumps(ctx['architecture'], indent=2)}\n"
            f"Permitted paths: {json.dumps(ctx['allowed_paths'])}"
        )
        agent_output = active_agent.run_json(
            stage="03_implementation",
            prompt=prompt,
            schema=IMPLEMENTATION_SCHEMA,
            workspace=staging,
            writable=True,
        )
        after = _file_hashes(staging)
        changed, deleted = _changed_paths(before, after)
        unexpected = [path for path in changed + deleted if not _is_allowed(path, normalized_allowed)]
        evidence = {
            **agent_output,
            "observed_changed_paths": changed,
            "observed_deleted_paths": deleted,
            "unexpected_paths": unexpected,
        }
        if deleted:
            return NodeResult(NodeStatus.FAILED, evidence, "File deletion is not permitted in this workflow.")
        if unexpected:
            return NodeResult(NodeStatus.FAILED, evidence, f"Agent changed paths outside the allowlist: {unexpected}")
        if not changed:
            return NodeResult(NodeStatus.FAILED, evidence, "Implementation produced no file changes.")
        ctx["staging_after"] = after
        ctx["changed_paths"] = changed
        return NodeResult(NodeStatus.SUCCEEDED, evidence)

    def validation_action(ctx: dict[str, Any]) -> NodeResult:
        python = repo / ".venv" / "Scripts" / "python.exe"
        if not python.exists():
            python = Path(sys.executable)
        checks = [
            ("pytest", [str(python), "-m", "pytest", "-q"]),
            ("compileall", [str(python), "-m", "compileall", "-q", "app", "orchestrator", "tests"]),
        ]
        results: list[dict[str, Any]] = []
        passed = True
        for name, command in checks:
            result = subprocess.run(
                command, 
                cwd=staging, 
                capture_output=True, 
                text=True,     
                encoding="utf-8",
                errors="replace", 
                timeout=300, 
                check=False)
            check = {
                "name": name,
                "command": command,
                "exit_code": result.returncode,
                "stdout": _short_output(result.stdout),
                "stderr": _short_output(result.stderr),
            }
            results.append(check)
            passed = passed and result.returncode == 0
        output = {"passed": passed, "checks": results}
        return NodeResult(
            NodeStatus.SUCCEEDED if passed else NodeStatus.FAILED,
            output,
            None if passed else "One or more deterministic validation checks failed.",
        )

    def review_action(ctx: dict[str, Any]) -> NodeResult:
        changed = ctx.get("changed_paths", [])
        prompt = (
            "Act as an independent code-review and risk agent. Review only; do not edit files. Inspect the changed "
            "files and evaluate correctness, requirement coverage, maintainability, security, regression risk, and "
            "test adequacy. Base the verdict on repository evidence and the real validation output. Request changes "
            "for any critical or high-severity issue.\n"
            f"Requirement: {ctx['requirement']}\nChanged paths: {json.dumps(changed)}\n"
            f"Validation evidence: {json.dumps(ctx['validation'], indent=2)}"
        )
        output = active_agent.run_json(
            stage="05_review", prompt=prompt, schema=REVIEW_SCHEMA, workspace=staging, writable=False
        )
        blocking = [item for item in output["findings"] if item["severity"] in {"critical", "high"}]
        if output["verdict"] != "approve" or blocking:
            return NodeResult(NodeStatus.FAILED, output, "Independent review requested changes.")
        return NodeResult(NodeStatus.SUCCEEDED, output)

    def release_action(ctx: dict[str, Any]) -> NodeResult:
        promoted: list[str] = []
        for relative in ctx["changed_paths"]:
            if not _is_allowed(relative, normalized_allowed):
                return NodeResult(NodeStatus.FAILED, {"promoted": promoted}, f"Blocked unexpected path: {relative}")
            source = staging / Path(relative)
            destination = repo / Path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            promoted.append(relative)
        return NodeResult(NodeStatus.SUCCEEDED, {"promoted_paths": promoted, "deployed": False})

    def approval(node: WorkflowNode, ctx: dict[str, Any]) -> bool:
        if node.node_id == "implementation":
            allowed = bool(ctx.get("approved_plan")) or approve(
                "Approve the requirements/design plan and allow Codex to edit the isolated staging copy?"
            )
            ctx["approved_plan"] = allowed
            return allowed
        if node.node_id == "release":
            allowed = bool(ctx.get("approved_release")) or approve(
                f"Validation and review passed. Promote {len(ctx.get('changed_paths', []))} allowlisted file(s) to the repository?"
            )
            ctx["approved_release"] = allowed
            return allowed
        return True

    nodes = [
        WorkflowNode(
            node_id="requirements",
            stage=Stage.REQUIREMENTS,
            title="Normalize the real requirement and acceptance criteria",
            deps=[],
            run=requirements_action,
            produces={"requirements"},
        ),
        WorkflowNode(
            node_id="architecture",
            stage=Stage.ARCHITECTURE,
            title="Analyze the real codebase and design the bounded change",
            deps=["requirements"],
            consumes={"requirements"},
            produces={"architecture"},
            run=architecture_action,
        ),
        WorkflowNode(
            node_id="implementation",
            stage=Stage.IMPLEMENTATION,
            title="Implement in an isolated staging workspace",
            deps=["architecture"],
            consumes={"requirements", "architecture"},
            produces={"code"},
            run=implementation_action,
            retry_policy=retry_policy(max_attempts=1, backoff_seconds=0.0),
            requires_approval=True,
        ),
        WorkflowNode(
            node_id="validation",
            stage=Stage.TESTING,
            title="Run real tests and compilation checks",
            deps=["implementation"],
            consumes={"code"},
            produces={"validation"},
            run=validation_action,
        ),
        WorkflowNode(
            node_id="review",
            stage=Stage.TESTING,
            title="Review the actual staged changes and validation evidence",
            deps=["validation"],
            consumes={"code", "validation"},
            produces={"review"},
            run=review_action,
        ),
        WorkflowNode(
            node_id="release",
            stage=Stage.RELEASE,
            title="Promote approved files without deployment",
            deps=["review"],
            consumes={"code", "validation", "review"},
            produces={"reviewable_outcome"},
            run=release_action,
            requires_approval=True,
        ),
    ]
    def evidence_guardrail(node: WorkflowNode, ctx: dict[str, Any]) -> tuple[bool, str]:
        if node.stage != Stage.RELEASE:
            return True, ""
        if ctx.get("validation", {}).get("passed") is not True:
            return False, "Release blocked because deterministic validation did not pass."
        if ctx.get("review", {}).get("verdict") != "approve":
            return False, "Release blocked because independent review did not approve the change."
        return True, ""

    policy = ExecutionPolicy(approval_callback=approval, guardrails=[evidence_guardrail], max_parallelism=2)
    report = WorkflowEngine("real-agentic-sdlc", nodes, policy=policy).execute(context=context)
    report_path = audit_root / "workflow_report.json"
    report_path.write_text(
        json.dumps(
            {
                "workflow_name": report.workflow_name,
                "status": report.status.value,
                "context": report.context,
                "events": [
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "node_id": event.node_id,
                        "action": event.action,
                        "detail": event.detail,
                    }
                    for event in report.events
                ],
                "metrics": {
                    "total_nodes": report.metrics.total_nodes,
                    "succeeded_nodes": report.metrics.succeeded_nodes,
                    "failed_nodes": report.metrics.failed_nodes,
                    "retried_nodes": report.metrics.retried_nodes,
                    "rolled_back_nodes": report.metrics.rolled_back_nodes,
                    "success_rate": report.metrics.success_rate,
                    "mttr_seconds": report.metrics.mttr_seconds,
                    "end_to_end_latency_seconds": report.metrics.end_to_end_latency_seconds,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
