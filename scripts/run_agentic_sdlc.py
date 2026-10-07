from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.real_workflow import run_real_agentic_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real, bounded Codex-backed SDLC workflow against an isolated staging copy."
    )
    requirement = parser.add_mutually_exclusive_group(required=True)
    requirement.add_argument("--requirement", help="Requirement text to implement.")
    requirement.add_argument("--requirement-file", type=Path, help="UTF-8 file containing the requirement.")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="PATH",
        help="Repository-relative file or directory the implementation agent may change. Repeat as needed.",
    )
    parser.add_argument("--approve-plan", action="store_true", help="Pre-approve editing the isolated copy.")
    parser.add_argument("--approve-release", action="store_true", help="Pre-approve promotion after checks pass.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = args.requirement
    if args.requirement_file:
        text = args.requirement_file.read_text(encoding="utf-8")
    report = run_real_agentic_workflow(
        repository=ROOT,
        requirement=text,
        allowed_paths=args.allow or ["app", "tests", "docs"],
        approve_plan=args.approve_plan,
        approve_release=args.approve_release,
    )
    print(f"Workflow status: {report.status.value}")
    print(f"Audit trail: {report.context['audit_directory']}")
    promoted = report.context.get("release", {}).get("promoted_paths", [])
    if promoted:
        print("Promoted files:")
        for path in promoted:
            print(f"  - {path}")
    return 0 if report.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
