from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.sample_workflows import (
    run_ambiguous_scenario,
    run_brownfield_scenario,
    run_greenfield_scenario,
)


def main() -> None:
    reports = [
        run_greenfield_scenario(),
        run_brownfield_scenario(),
        run_ambiguous_scenario(),
    ]

    output = []
    for report in reports:
        output.append(
            {
                "workflow_name": report.workflow_name,
                "status": report.status.value,
                "metrics": {
                    "success_rate": report.metrics.success_rate,
                    "retry_count": report.metrics.retried_nodes,
                    "rollback_count": report.metrics.rolled_back_nodes,
                    "mttr_seconds": report.metrics.mttr_seconds,
                    "latency_seconds": report.metrics.end_to_end_latency_seconds,
                },
                "event_count": len(report.events),
            }
        )

    output_path = Path("data/workflow_demo_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Saved workflow demo report to {output_path}")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
