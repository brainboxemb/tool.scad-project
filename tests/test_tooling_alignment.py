"""Exact SCAD tooling alignment

Checks:
When a generic project pins `tool.scad-project` by full commit SHA, tooling validation
rejects a different checked-out gitlink. Consumer Build/Verify/Release workflow callers
must also use that exact checked-out commit rather than a stale tag, branch or SHA.

Testing approach:
Tests build temporary consumer layouts, replace Git SHA lookup with deterministic output,
and run the real tooling validator. No remote repository or workflow execution is
required.
"""

from pathlib import Path
from types import SimpleNamespace

import scad_project.tooling as tooling
from scad_project.config import ProjectContext


def _context(tmp_path: Path, expected: str) -> ProjectContext:
    tool_root = tmp_path / "tools" / "tool.scad-project"
    tool_root.mkdir(parents=True)
    return ProjectContext(
        tmp_path,
        tmp_path / "project.scad.yml",
        {
            "tooling": {
                "tool_scad_project": {
                    "path": "tools/tool.scad-project",
                    "ref": expected,
                }
            }
        },
    )


def _git_sha(monkeypatch, sha: str):
    monkeypatch.setattr(
        tooling.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=sha + "\n",
            stderr="",
        ),
    )


def test_exact_dependency_ref_must_match_checked_out_gitlink(tmp_path, monkeypatch):
    expected = "1" * 40
    actual = "2" * 40
    context = _context(tmp_path, expected)
    _git_sha(monkeypatch, actual)

    errors = tooling.tooling_errors(context)

    assert any("gitlink mismatch" in error for error in errors)


def test_external_workflow_callers_must_match_checked_out_tool_sha(
    tmp_path, monkeypatch
):
    sha = "3" * 40
    context = _context(tmp_path, sha)
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "build.yml").write_text(
        "jobs:\n  build:\n    uses: "
        "brainboxemb/tool.scad-project/.github/workflows/project-build.yml@stale\n",
        encoding="utf-8",
    )
    _git_sha(monkeypatch, sha)

    errors = tooling.tooling_errors(context)

    assert any("workflow ref mismatch" in error for error in errors)


def test_aligned_exact_gitlink_and_workflow_pass(tmp_path, monkeypatch):
    sha = "4" * 40
    context = _context(tmp_path, sha)
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "build.yml").write_text(
        "jobs:\n  build:\n    uses: "
        f"brainboxemb/tool.scad-project/.github/workflows/project-build.yml@{sha}\n",
        encoding="utf-8",
    )
    _git_sha(monkeypatch, sha)

    assert tooling.tooling_errors(context) == []
