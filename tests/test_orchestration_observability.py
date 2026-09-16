"""Durable Migration-005 producer and orchestration observability.

Checks:
Producer execution evidence records the timing context supplied by the shared
Moon capability wrapper. Publication staging keeps current preflight and raw
Moon invocation evidence, writes current-run/snapshot-preparation timing, and
refreshes generated README navigation with direct links to the retained files.

Testing approach:
Use temporary output/preflight trees, deterministic producer timing and the real
publication-staging helper. Assertions distinguish producer execution timing,
current Moon materialization evidence and current snapshot-preparation timing.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.execution_evidence import write_execution_evidence


ROOT = Path(__file__).resolve().parents[1]
STAGE_SCRIPT = ROOT / "scripts" / "stage_publication.py"


def _context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={
            "paths": {"build_root": "bld"},
            "tooling": {
                "tool_scad_project": {"path": "tools/tool.scad-project"},
            },
        },
    )


def _stage_module():
    spec = importlib.util.spec_from_file_location("stage_publication", STAGE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execution_evidence_records_producer_timing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", "1" * 40)
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", "2" * 40)
    monkeypatch.setenv("SCAD_PROJECT_PRODUCER_STARTED_AT", "2026-09-16T07:00:00Z")
    monkeypatch.setenv("SCAD_PROJECT_PRODUCER_STARTED_MONOTONIC_NS", "1000000000")
    monkeypatch.setattr(
        "scad_project.execution_evidence.time.monotonic_ns",
        lambda: 1234000000,
    )
    monkeypatch.setattr(
        "scad_project.execution_evidence._utc_now",
        lambda: "2026-09-16T07:00:01Z",
    )

    output = write_execution_evidence(
        _context(tmp_path),
        capability="scad.build",
        action="build",
        execution_id="scad-build",
        output_root=tmp_path / "bld",
    )
    assert output is not None
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["producer_execution"] == {
        "started_at": "2026-09-16T07:00:00Z",
        "finished_at": "2026-09-16T07:00:01Z",
        "duration_ms": 234,
    }
    log = (output.parent / "execution.log").read_text(encoding="utf-8")
    assert "Producer duration: 234 ms" in log


def test_publication_staging_preserves_current_logs_and_links_them(
    tmp_path: Path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    source_root = workspace / "bld"
    source_root.mkdir(parents=True)
    (source_root / "README.md").write_text(
        "# Generated build output\n\n## Artifacts\n\n- render\n",
        encoding="utf-8",
    )

    preflight = workspace / ".moon" / "preflight"
    preflight.mkdir(parents=True)
    (preflight / "decision.json").write_text('{"status":"success"}\n', encoding="utf-8")
    (preflight / "affected-task-ids.json").write_text('["consumer:scad.build"]\n', encoding="utf-8")
    (preflight / "scad-ci-plan.json").write_text('{"run_runtime":true}\n', encoding="utf-8")

    invocation = workspace / ".moon" / "invocations" / "consumer_scad.build"
    invocation.mkdir(parents=True)
    (invocation / "materialization.json").write_text(
        '{"task":"consumer:scad.build","duration_ms":42}\n',
        encoding="utf-8",
    )
    (invocation / "moon.log").write_text(
        "Tasks: 1 completed (1 cached)\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("GITHUB_REPOSITORY", "brainboxemb/example")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

    stage = _stage_module()
    staging_root = tmp_path / "staged-build"
    run_context = stage.stage_publication(
        source_root=source_root,
        staging_root=staging_root,
        family="build",
        source_sha="3" * 40,
        base_sha="4" * 40,
        workspace=workspace,
    )

    context = json.loads(run_context.read_text(encoding="utf-8"))
    assert context["schema"] == "brainboxemb.scad-orchestration-run-context"
    assert context["publication_family"] == "build"
    assert context["repository"] == "brainboxemb/example"
    assert context["run_id"] == "123"
    assert context["run_attempt"] == "2"
    assert context["source_revision"] == "3" * 40
    assert context["base_revision"] == "4" * 40
    assert context["snapshot_preparation"]["started_at"].endswith("Z")
    assert context["snapshot_preparation"]["finished_at"].endswith("Z")
    assert isinstance(context["snapshot_preparation"]["duration_ms"], int)

    orchestration = staging_root / "orchestration"
    assert (orchestration / "impact-decision.json").is_file()
    assert (orchestration / "affected-task-ids.json").is_file()
    assert (orchestration / "scad-ci-plan.json").is_file()
    assert (
        orchestration
        / "moon-invocations"
        / "consumer_scad.build"
        / "materialization.json"
    ).is_file()
    assert (
        orchestration
        / "moon-invocations"
        / "consumer_scad.build"
        / "moon.log"
    ).is_file()

    readme = (staging_root / "README.md").read_text(encoding="utf-8")
    assert "orchestration/run-context.json" in readme
    assert "orchestration/impact-decision.json" in readme
    assert "consumer_scad.build/materialization.json" in readme
    assert "consumer_scad.build/moon.log" in readme
    assert "raw Moon/producer log" in readme
