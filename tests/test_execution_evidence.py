"""Persistent SCAD producer execution evidence.

Checks:
SCAD producer evidence uses the shared schema-v1 field contract, retains one
canonical human-readable log, copies richer SCons decision telemetry as domain
evidence, preserves exact source/owner revisions, and adds readable navigation
without duplicating evidence. Local non-Git builds remain usable and simply skip
persistent evidence when exact revisions cannot be resolved.

Testing approach:
The tests use temporary project/output trees and explicit fake source/owner revision
environment values. A representative SCons decision report verifies copied domain
evidence and concise log summarization. Separate cases remove Git/revision context to
prove local compatibility and append navigation twice to prove deterministic,
idempotent generated README content.
"""

from __future__ import annotations

import json
from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.execution_evidence import (
    append_evidence_navigation,
    evidence_navigation_lines,
    write_execution_evidence,
)


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


def _report(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "scad-project.build-decisions",
                "schema_version": 1,
                "kind": "build",
                "engine": "scons",
                "target_count": 2,
                "outcome_counts": {
                    "BUILT": 1,
                    "CACHE_RESTORED": 0,
                    "CURRENT": 1,
                    "ERROR": 0,
                },
                "targets": [
                    {"output": "bld/png/a.png", "outcome": "BUILT"},
                    {"output": "bld/stl/b.stl", "outcome": "CURRENT"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_execution_evidence_retains_common_envelope_and_domain_report(
    tmp_path: Path,
    monkeypatch,
):
    source_revision = "1" * 40
    owner_revision = "2" * 40
    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", source_revision)
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", owner_revision)

    output_root = tmp_path / "bld"
    report = _report(tmp_path / ".cache/scad-project/state/last-build.json")
    output = write_execution_evidence(
        _context(tmp_path),
        capability="scad.build",
        action="build",
        execution_id="scad-build",
        output_root=output_root,
        domain_report=report,
    )

    assert output == output_root / "evidence/executions/scad-build/execution.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "brainboxemb.execution-evidence"
    assert payload["schema_version"] == 1
    assert payload["capability"] == "scad.build"
    assert payload["owner"] == "brainboxemb/tool.scad-project"
    assert payload["action"] == "build"
    assert payload["source_revision"] == source_revision
    assert payload["owner_revision"] == owner_revision
    assert payload["status"] == "success"
    assert payload["exit_code"] == 0
    assert payload["log"] == "execution.log"
    assert payload["domain_evidence"] == ["../../domain/last-build.json"]

    canonical_log = output.parent / "execution.log"
    assert canonical_log.is_file()
    assert not (output_root / "evidence/execution.log").exists()
    text = canonical_log.read_text(encoding="utf-8")
    assert "Outcomes: BUILT=1, CACHE_RESTORED=0, CURRENT=1, ERROR=0" in text
    assert "- BUILT: bld/png/a.png" in text
    assert "- CURRENT: bld/stl/b.stl" in text
    assert (output_root / "evidence/domain/last-build.json").is_file()


def test_execution_evidence_skips_unversioned_local_context(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    monkeypatch.delenv("SCAD_PROJECT_SOURCE_SHA", raising=False)
    monkeypatch.delenv("SCAD_PROJECT_TOOL_SHA", raising=False)
    monkeypatch.setattr(
        "scad_project.execution_evidence._git_head",
        lambda path: None,
    )

    output = write_execution_evidence(
        _context(tmp_path),
        capability="scad.build",
        action="build",
        execution_id="scad-build",
        output_root=tmp_path / "bld",
    )

    assert output is None
    assert not (tmp_path / "bld/evidence").exists()
    assert "persistent SCAD execution evidence skipped" in capsys.readouterr().out


def test_navigation_is_readable_and_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", "3" * 40)
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", "4" * 40)
    output_root = tmp_path / "bld"
    readme = output_root / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text("# Generated build output\n\n## Artifacts\n\n- render\n", encoding="utf-8")

    write_execution_evidence(
        _context(tmp_path),
        capability="scad.build",
        action="build",
        execution_id="scad-build",
        output_root=output_root,
        domain_report=_report(tmp_path / ".cache/state/last-build.json"),
    )
    append_evidence_navigation(readme, output_root)
    append_evidence_navigation(readme, output_root)

    text = readme.read_text(encoding="utf-8")
    assert text.count("<!-- scad-project-evidence-navigation -->") == 1
    assert "## Producer execution evidence" in text
    assert "## Domain evidence" in text
    assert "## Orchestration/materialization evidence" in text
    assert "## Publication context" in text
    assert "evidence/executions/scad-build/execution.json" in text
    assert "evidence/domain/last-build.json" in text

    without_publication = "\n".join(
        evidence_navigation_lines(output_root, include_publication_context=False)
    )
    assert "## Publication context" not in without_publication


def test_execution_evidence_links_multiple_domain_reports(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("SCAD_PROJECT_SOURCE_SHA", "5" * 40)
    monkeypatch.setenv("SCAD_PROJECT_TOOL_SHA", "6" * 40)

    state = tmp_path / ".cache/state"
    state.mkdir(parents=True)
    decision = state / "last-build.json"
    decision.write_text(
        json.dumps(
            {
                "kind": "build",
                "engine": "scons",
                "target_count": 0,
                "outcome_counts": {
                    "BUILT": 0,
                    "CACHE_RESTORED": 0,
                    "CURRENT": 0,
                    "ERROR": 0,
                },
                "targets": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    provenance = state / "dependency-provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "schema": "brainboxemb.scad-build-dependency-provenance",
                "schema_version": 1,
                "targets": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    output_root = tmp_path / "bld"
    output = write_execution_evidence(
        _context(tmp_path),
        capability="scad.build",
        action="build",
        execution_id="scad-build",
        output_root=output_root,
        domain_reports=[decision, provenance],
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["domain_evidence"] == [
        "../../domain/last-build.json",
        "../../domain/dependency-provenance.json",
    ]
    assert (output_root / "evidence/domain/last-build.json").is_file()
    assert (output_root / "evidence/domain/dependency-provenance.json").is_file()

    log = (output.parent / "execution.log").read_text(encoding="utf-8")
    assert "Domain evidence:" in log
    assert "- ../../domain/last-build.json" in log
    assert "- ../../domain/dependency-provenance.json" in log
