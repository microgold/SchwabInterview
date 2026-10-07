from __future__ import annotations

import json
from html import escape
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


def _format_number(value: object, digits: int = 2) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _build_html_report(workflows: list[dict[str, object]]) -> str:
    cards = []
    for workflow in workflows:
        metrics = workflow["metrics"]
        assert isinstance(metrics, dict)
        status = str(workflow["status"])
        status_class = "success" if status.lower() == "succeeded" else "failed"

        metric_items = "".join(
            f"<div class=\"metric\"><span>{escape(label)}</span>"
            f"<strong>{escape(_format_number(value))}</strong></div>"
            for label, value in (
                ("Success rate", metrics["success_rate"]),
                ("Retries", metrics["retry_count"]),
                ("Rollbacks", metrics["rollback_count"]),
                ("MTTR (seconds)", metrics["mttr_seconds"]),
                ("Latency (seconds)", metrics["latency_seconds"]),
                ("Events", workflow["event_count"]),
            )
        )
        cards.append(
            "<article class=\"workflow-card\">"
            "<header>"
            f"<h2>{escape(str(workflow['workflow_name']))}</h2>"
            f"<span class=\"status {status_class}\">{escape(status)}</span>"
            "</header>"
            f"<div class=\"metrics\">{metric_items}</div>"
            "</article>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workflow Demo Report</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; background: #f3f5f8; color: #172033; }}
    main {{ width: min(1100px, calc(100% - 32px)); margin: 48px auto; }}
    .page-header {{ margin-bottom: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.25rem); }}
    .subtitle {{ margin: 0; color: #62708a; }}
    .report-grid {{ display: grid; gap: 20px; }}
    .workflow-card {{ background: #fff; border: 1px solid #dde3ec; border-radius: 16px;
      padding: 24px; box-shadow: 0 10px 30px rgba(29, 42, 68, .07); }}
    .workflow-card header {{ display: flex; align-items: center; justify-content: space-between;
      gap: 16px; margin-bottom: 20px; }}
    h2 {{ margin: 0; font-size: 1.25rem; }}
    .status {{ padding: 6px 10px; border-radius: 999px; font-size: .78rem;
      font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }}
    .status.success {{ background: #dff7e8; color: #12653a; }}
    .status.failed {{ background: #ffe2e2; color: #9f1d1d; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 12px; }}
    .metric {{ background: #f7f9fc; border-radius: 10px; padding: 14px; }}
    .metric span {{ display: block; color: #68758c; font-size: .78rem; margin-bottom: 5px; }}
    .metric strong {{ font-size: 1.15rem; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #0e1420; color: #edf2f8; }}
      .subtitle {{ color: #9eabc0; }}
      .workflow-card {{ background: #171f2e; border-color: #2c374a; box-shadow: none; }}
      .metric {{ background: #202a3b; }}
      .metric span {{ color: #aeb9ca; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="page-header">
      <h1>Workflow Demo Report</h1>
      <p class="subtitle">Summary of the greenfield, brownfield, and ambiguous workflow scenarios.</p>
    </header>
    <section class="report-grid" aria-label="Workflow results">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>
"""


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
    html_path = output_path.with_suffix(".html")
    html_path.write_text(_build_html_report(output), encoding="utf-8")
    print(f"Saved workflow demo report to {output_path}")
    print(f"Saved HTML workflow demo report to {html_path}")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
