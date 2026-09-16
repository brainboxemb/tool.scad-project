"""Durable SCAD workflow timing evidence.

Checks:
Contiguous phase transitions retain UTC boundaries and exact millisecond durations;
the first transition can bootstrap from the workflow start recorded before checkout;
invalid phase ordering fails instead of silently rewriting evidence; and family-specific
snapshot timing appends snapshot preparation and total-to-snapshot duration without
mutating the base workflow timing file.

Testing approach:
Use temporary timing files and explicit UTC boundaries so phase ordering, durations,
closed/open phase transitions and snapshot copies can be asserted deterministically
without depending on wall-clock time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scad_project.workflow_timing import (
    begin_phase,
    snapshot_timings,
    transition_phase,
)


def test_transitions_record_contiguous_workflow_phases(tmp_path: Path):
    path = tmp_path / "workflow-timings.json"
    started = "2026-09-16T09:00:00.000Z"

    transition_phase(
        path,
        finish="preflight_and_plan",
        begin="cache_restore",
        workflow_started_at=started,
        now="2026-09-16T09:00:02.500Z",
    )
    transition_phase(
        path,
        finish="cache_restore",
        begin="runtime_pull",
        now="2026-09-16T09:00:03.000Z",
    )
    transition_phase(
        path,
        finish="runtime_pull",
        now="2026-09-16T09:00:05.250Z",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "brainboxemb.scad-workflow-timings"
    assert payload["schema_version"] == 1
    assert payload["workflow_started_at"] == started
    assert "active_phase" not in payload
    assert [phase["name"] for phase in payload["phases"]] == [
        "preflight_and_plan",
        "cache_restore",
        "runtime_pull",
    ]
    assert [phase["duration_ms"] for phase in payload["phases"]] == [2500, 500, 2250]


def test_phase_order_mismatch_is_rejected(tmp_path: Path):
    path = tmp_path / "workflow-timings.json"
    transition_phase(
        path,
        finish="preflight_and_plan",
        begin="cache_restore",
        workflow_started_at="2026-09-16T09:00:00.000Z",
        now="2026-09-16T09:00:01.000Z",
    )

    with pytest.raises(RuntimeError, match="active phase is 'cache_restore'"):
        transition_phase(
            path,
            finish="materialization",
            now="2026-09-16T09:00:02.000Z",
        )


def test_begin_phase_requires_closed_sequence(tmp_path: Path):
    path = tmp_path / "workflow-timings.json"
    transition_phase(
        path,
        finish="preflight_and_plan",
        workflow_started_at="2026-09-16T09:00:00.000Z",
        now="2026-09-16T09:00:01.000Z",
    )
    begin_phase(path, phase="publication", now="2026-09-16T09:00:02.000Z")

    with pytest.raises(RuntimeError, match="another phase is active"):
        begin_phase(path, phase="other", now="2026-09-16T09:00:03.000Z")


def test_snapshot_appends_family_specific_timing_without_mutating_base(tmp_path: Path):
    path = tmp_path / "workflow-timings.json"
    transition_phase(
        path,
        finish="preflight_and_plan",
        begin="materialization",
        workflow_started_at="2026-09-16T09:00:00.000Z",
        now="2026-09-16T09:00:02.000Z",
    )
    transition_phase(
        path,
        finish="materialization",
        now="2026-09-16T09:00:05.000Z",
    )

    snapshot = snapshot_timings(
        path,
        publication_family="build",
        snapshot_started_at="2026-09-16T09:00:06.000Z",
        snapshot_finished_at="2026-09-16T09:00:06.125Z",
        snapshot_duration_ms=123,
    )

    assert snapshot["publication_family"] == "build"
    assert snapshot["snapshot_ready_at"] == "2026-09-16T09:00:06.125Z"
    assert snapshot["total_to_snapshot_ms"] == 6125
    assert snapshot["phases"][-1] == {
        "name": "snapshot_preparation",
        "started_at": "2026-09-16T09:00:06.000Z",
        "finished_at": "2026-09-16T09:00:06.125Z",
        "duration_ms": 123,
    }

    base = json.loads(path.read_text(encoding="utf-8"))
    assert [phase["name"] for phase in base["phases"]] == [
        "preflight_and_plan",
        "materialization",
    ]
