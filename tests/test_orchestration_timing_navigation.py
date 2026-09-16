"""Generated output navigation for durable orchestration timings.

Checks:
A published `timings.json` is linked from the generated README and rendered as a
compact phase table without replacing the detailed Moon materialization and raw-log
links.

Testing approach:
Build a minimal generated-output tree with deterministic timing JSON plus one Moon
invocation, refresh the real evidence navigation, and assert the human-facing table,
total timing, direct raw-log link and snapshot/publication boundary text.
"""

from __future__ import annotations

import json
from pathlib import Path

from scad_project.execution_evidence import append_evidence_navigation


def test_generated_navigation_renders_workflow_timing_table(tmp_path: Path):
    output = tmp_path / "bld"
    orchestration = output / "orchestration"
    invocation = orchestration / "moon-invocations/consumer_scad.build"
    invocation.mkdir(parents=True)
    output.joinpath("README.md").write_text("# Build\n", encoding="utf-8")
    invocation.joinpath("materialization.json").write_text("{}\n", encoding="utf-8")
    invocation.joinpath("moon.log").write_text("raw build log\n", encoding="utf-8")
    orchestration.joinpath("timings.json").write_text(
        json.dumps(
            {
                "schema": "brainboxemb.scad-workflow-timings",
                "schema_version": 1,
                "workflow_started_at": "2026-09-16T09:00:00.000Z",
                "publication_family": "build",
                "snapshot_ready_at": "2026-09-16T09:00:05.500Z",
                "total_to_snapshot_ms": 5500,
                "phases": [
                    {"name": "preflight_and_plan", "duration_ms": 1250},
                    {"name": "runtime_pull", "duration_ms": 3000},
                    {"name": "materialization", "duration_ms": 900},
                    {"name": "snapshot_preparation", "duration_ms": 25},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    append_evidence_navigation(output / "README.md", output)
    text = (output / "README.md").read_text(encoding="utf-8")

    assert "[Workflow phase timings](orchestration/timings.json)" in text
    assert "### Current workflow timing" in text
    assert "| Preflight + execution plan | 1.250 s |" in text
    assert "| Runtime pull | 3.000 s |" in text
    assert "| Capability materialization | 900 ms |" in text
    assert "| **Total to prepared snapshot** | **5.500 s** |" in text
    assert "consumer:scad.build raw Moon/producer log" in text
    assert "remote branch push happens afterwards" in text
