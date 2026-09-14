"""CLI coverage for explicit post-build decision audits."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scad_project import build_decisions
from scad_project import cli


def _decision_report(outcome: str, sources: list[str]) -> dict:
    return {
        "schema": build_decisions.REPORT_SCHEMA,
        "schema_version": build_decisions.REPORT_SCHEMA_VERSION,
        "kind": "build",
        "engine": "scons",
        "targets": [
            {
                "output": "bld/part.stl",
                "outcome": outcome,
                "sources": sources,
            }
        ],
    }


def _prepare_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_context", lambda _: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr(cli, "validate_config", lambda _: [])
    monkeypatch.setattr(cli, "validate_build_engine_config", lambda _: [])
    monkeypatch.setattr(cli, "validate_release_config", lambda _: [])


def test_build_audit_cli_combines_direct_and_file_changes(monkeypatch, tmp_path):
    _prepare_cli(monkeypatch, tmp_path)
    state = tmp_path / ".cache" / "scad-project" / "state"
    state.mkdir(parents=True)
    report_path = state / "last-build.json"
    report_path.write_text(
        json.dumps(_decision_report("BUILT", ["dsg/main.scad", "dsg/shared.scad"])),
        encoding="utf-8",
    )
    changed_file = tmp_path / "changed.txt"
    changed_file.write_text("README.md\ndsg/shared.scad\n", encoding="utf-8")

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "scad-project",
            "--project",
            str(tmp_path),
            "build-audit",
            "--report",
            ".cache/scad-project/state/last-build.json",
            "--changed-path",
            "./dsg/main.scad",
            "--changed-paths-file",
            "changed.txt",
        ],
    )

    cli.main()

    output = state / "last-build-audit.json"
    audit = json.loads(output.read_text(encoding="utf-8"))
    assert audit["result"] == "PASS"
    assert audit["changed_paths"] == [
        "README.md",
        "dsg/main.scad",
        "dsg/shared.scad",
    ]
    assert audit["targets"][0]["matched_changed_sources"] == [
        "dsg/main.scad",
        "dsg/shared.scad",
    ]


def test_build_audit_cli_warning_exits_zero_and_supports_explicit_output(
    monkeypatch, tmp_path
):
    _prepare_cli(monkeypatch, tmp_path)
    report = tmp_path / "decision.json"
    report.write_text(
        json.dumps(_decision_report("BUILT", ["dsg/main.scad"])),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "scad-project",
            "--project",
            str(tmp_path),
            "build-audit",
            "--report",
            "decision.json",
            "--changed-path",
            "README.md",
            "--output",
            "evidence/custom-audit.json",
        ],
    )

    cli.main()

    audit = json.loads(
        (tmp_path / "evidence" / "custom-audit.json").read_text(encoding="utf-8")
    )
    assert audit["result"] == "PASS"
    assert audit["audit_counts"]["WARNING"] == 1


def test_build_audit_cli_failure_writes_evidence_then_exits_one(monkeypatch, tmp_path):
    _prepare_cli(monkeypatch, tmp_path)
    report = tmp_path / "decision.json"
    report.write_text(
        json.dumps(_decision_report("CURRENT", ["dsg/main.scad"])),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "scad-project",
            "--project",
            str(tmp_path),
            "build-audit",
            "--report",
            "decision.json",
            "--changed-path",
            "dsg/main.scad",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    audit = json.loads((tmp_path / "decision-audit.json").read_text(encoding="utf-8"))
    assert audit["result"] == "FAIL"
    assert audit["targets"][0]["reason"] == "PROVEN_LEFT_CURRENT"


def test_build_audit_cli_requires_changed_path_input(monkeypatch, tmp_path):
    _prepare_cli(monkeypatch, tmp_path)
    report = tmp_path / "decision.json"
    report.write_text(
        json.dumps(_decision_report("CURRENT", ["dsg/main.scad"])),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "scad-project",
            "--project",
            str(tmp_path),
            "build-audit",
            "--report",
            "decision.json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
