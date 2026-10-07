from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.models import NodeStatus
from orchestrator.real_workflow import run_real_agentic_workflow


class FakeAgent:
    def __init__(self, unexpected_change: bool = False) -> None:
        self.unexpected_change = unexpected_change

    def run_json(
        self,
        *,
        stage: str,
        prompt: str,
        schema: dict[str, Any],
        workspace: Path,
        writable: bool,
    ) -> dict[str, Any]:
        _ = prompt, schema, writable
        if stage == "01_requirements":
            return {
                "normalized_requirement": "Return a stable greeting.",
                "ambiguities": [],
                "acceptance_criteria": ["The greeting is covered by a passing test."],
                "tasks": ["Update the implementation and test."],
                "impacted_paths": ["app/demo.py", "tests/test_demo.py"],
                "risks": ["A regression could change the public return value."],
            }
        if stage == "02_architecture":
            return {
                "design_summary": "Change the function and assert its result.",
                "data_flow": ["test -> greeting"],
                "decisions": ["Keep the function deterministic."],
                "validation_plan": ["Run pytest and compileall."],
                "files_expected_to_change": ["app/demo.py", "tests/test_demo.py"],
            }
        if stage == "03_implementation":
            (workspace / "app" / "demo.py").write_text(
                'def greeting() -> str:\n    return "hello"\n', encoding="utf-8"
            )
            (workspace / "tests" / "test_demo.py").write_text(
                'from app.demo import greeting\n\n\ndef test_greeting() -> None:\n    assert greeting() == "hello"\n',
                encoding="utf-8",
            )
            if self.unexpected_change:
                (workspace / "README.md").write_text("unexpected\n", encoding="utf-8")
            return {
                "summary": "Implemented the greeting and its test.",
                "files_changed": ["app/demo.py", "tests/test_demo.py"],
                "tests_added_or_updated": ["tests/test_demo.py"],
                "known_limitations": [],
            }
        if stage == "05_review":
            return {
                "verdict": "approve",
                "findings": [],
                "requirement_coverage": ["The test covers the required greeting."],
                "residual_risks": [],
            }
        raise AssertionError(f"Unexpected stage: {stage}")


def _make_repository(root: Path) -> None:
    (root / "app").mkdir()
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "demo.py").write_text(
        'def greeting() -> str:\n    return "old"\n', encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_demo.py").write_text(
        'from app.demo import greeting\n\n\ndef test_greeting() -> None:\n    assert greeting() == "old"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("original\n", encoding="utf-8")


def test_real_workflow_validates_and_promotes_allowlisted_changes(tmp_path: Path) -> None:
    _make_repository(tmp_path)

    report = run_real_agentic_workflow(
        repository=tmp_path,
        requirement="Return hello from greeting.",
        allowed_paths=["app", "tests"],
        approve_plan=True,
        approve_release=True,
        agent=FakeAgent(),  # type: ignore[arg-type]
    )

    assert report.status == NodeStatus.SUCCEEDED
    assert 'return "hello"' in (tmp_path / "app" / "demo.py").read_text(encoding="utf-8")
    assert report.context["validation"]["passed"] is True
    assert report.context["review"]["verdict"] == "approve"
    assert report.context["release"]["deployed"] is False


def test_real_workflow_blocks_changes_outside_allowlist(tmp_path: Path) -> None:
    _make_repository(tmp_path)

    report = run_real_agentic_workflow(
        repository=tmp_path,
        requirement="Return hello from greeting.",
        allowed_paths=["app", "tests"],
        approve_plan=True,
        approve_release=True,
        agent=FakeAgent(unexpected_change=True),  # type: ignore[arg-type]
    )

    assert report.status == NodeStatus.FAILED
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "original\n"
    assert report.context["implementation"]["unexpected_paths"] == ["README.md"]
