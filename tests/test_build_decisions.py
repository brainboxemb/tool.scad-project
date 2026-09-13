"""Structured build-decision telemetry

Checks:
The shared report contract classifies successful action execution as BUILT, fresh
CacheDir materialization as CACHE_RESTORED, pre-existing up-to-date output as CURRENT,
and missing/invalid output as ERROR. Reports expose compatible schema/version fields,
per-target source/spec evidence, outcome counts, and available workflow provenance.

Testing approach:
The tests use temporary manifest/output files and an execution log rather than starting
SCons. This isolates classification/report serialization from the later deterministic
SCons decision matrix planned for Step 2.
"""

from __future__ import annotations

import json
from pathlib import Path

from scad_project import build_decisions


def test_outcome_classification_matrix():
    assert build_decisions.classify_outcome(
        executed=True, existed_before=False, exists_after=True
    ) == "BUILT"
    assert build_decisions.classify_outcome(
        executed=False, existed_before=False, exists_after=True
    ) == "CACHE_RESTORED"
    assert build_decisions.classify_outcome(
        executed=False, existed_before=True, exists_after=True
    ) == "CURRENT"
    assert build_decisions.classify_outcome(
        executed=False, existed_before=False, exists_after=False
    ) == "ERROR"
    assert build_decisions.classify_outcome(
        executed=True, existed_before=True, exists_after=False
    ) == "ERROR"


def test_report_serializes_target_outcomes_and_provenance(tmp_path: Path, monkeypatch):
    state = tmp_path / ".cache" / "scad-project" / "state"
    state.mkdir(parents=True)
    execution_log = state / "executed-targets.txt"
    execution_log.write_text("bld/a.out\n", encoding="utf-8")

    for relative in ("bld/a.out", "bld/b.out", "bld/c.out"):
        output = tmp_path / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(relative, encoding="utf-8")

    manifest = state / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_log": str(execution_log),
                "targets": [
                    {
                        "output": "bld/a.out",
                        "source": "dsg/a.scad",
                        "sources": ["dsg/a.scad", "dsg/shared.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": False,
                    },
                    {
                        "output": "bld/b.out",
                        "source": "dsg/b.scad",
                        "sources": ["dsg/b.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": False,
                    },
                    {
                        "output": "bld/c.out",
                        "source": "dsg/c.scad",
                        "sources": ["dsg/c.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": True,
                    },
                    {
                        "output": "bld/d.out",
                        "source": "dsg/d.scad",
                        "sources": ["dsg/d.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", "source-sha")
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", "tool-sha")
    monkeypatch.setenv("SCAD_TOOLCHAIN_IMAGE", "toolchain:image")
    monkeypatch.setenv("SCAD_TOOLCHAIN_VERSION", "toolchain-version")
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "workflow-version")
    monkeypatch.setenv("SCAD_PROJECT_CACHE_NAMESPACE", "cache-space")
    monkeypatch.setenv("SCAD_PROJECT_CACHE_PRIMARY_KEY", "cache-primary")
    monkeypatch.setenv("SCAD_PROJECT_CACHE_MATCHED_KEY", "cache-match")
    monkeypatch.setenv("SCAD_PROJECT_CACHE_HIT", "false")

    report_path = state / "last-build.json"
    report = build_decisions.write_decision_report(
        project_root=tmp_path,
        manifest=manifest,
        report_path=report_path,
        report_kind="build",
        backend_signature="backend-test",
    )

    assert report_path.is_file()
    assert report["schema"] == "scad-project.build-decisions"
    assert report["schema_version"] == 1
    assert report["manifest_schema_version"] == 1
    assert report["kind"] == "build"
    assert report["target_count"] == 4
    assert report["outcome_counts"] == {
        "BUILT": 1,
        "CACHE_RESTORED": 1,
        "CURRENT": 1,
        "ERROR": 1,
    }
    assert [target["outcome"] for target in report["targets"]] == [
        "BUILT",
        "CACHE_RESTORED",
        "CURRENT",
        "ERROR",
    ]
    assert report["targets"][0]["sources"] == ["dsg/a.scad", "dsg/shared.scad"]
    assert len(report["targets"][0]["target_spec_digest"]) == 64
    assert report["provenance"]["source_commit_sha"] == "source-sha"
    assert report["provenance"]["tool_commit_sha"] == "tool-sha"
    assert report["provenance"]["cache"] == {
        "namespace": "cache-space",
        "primary_key": "cache-primary",
        "matched_key": "cache-match",
        "exact_hit": False,
    }


def test_capture_output_state_does_not_change_target_digest_input(tmp_path: Path):
    output = tmp_path / "bld" / "part.out"
    output.parent.mkdir(parents=True)
    output.write_text("present", encoding="utf-8")
    target = {"output": "bld/part.out", "source": "part.scad", "flags": ["--render"]}

    original_digest = build_decisions.target_spec_digest(target)
    build_decisions.capture_output_state(tmp_path, [target])
    digest_source = {key: value for key, value in target.items() if key != "existed_before"}

    assert target["existed_before"] is True
    assert build_decisions.target_spec_digest(digest_source) == original_digest
