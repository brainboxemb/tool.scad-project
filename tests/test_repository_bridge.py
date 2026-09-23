"""Generic repository-tool delegation.

Checks:
Repository bootstrap/status/update operations are delegated to the pinned
`tool.git-project` checkout instead of being reimplemented by the SCAD tool. After a
generic update, SCAD reusable Build, Verify, CI and Release workflow callers
are aligned to the configured `tool.scad-project` ref instead of an opaque checked-out
commit SHA.

Testing approach:
Tests create small temporary repository layouts and replace command execution with
deterministic test doubles. They inspect the exact delegated command and workflow-file
rewrite without contacting GitHub or changing real submodules.
"""

from pathlib import Path

from scad_project import __version__
import scad_project.repository as repository
from scad_project.config import ProjectContext


def _context(tmp_path: Path, *, tool_ref: str | None = None) -> ProjectContext:
    ref = tool_ref or f"v{__version__}"
    return ProjectContext(
        tmp_path,
        tmp_path / "project.scad.yml",
        {
            "project": {"name": "demo"},
            "tooling": {
                "tool_scad_project": {
                    "path": "tools/tool.scad-project",
                    "ref": ref,
                }
            },
        },
        repository_config={"project": {"name": "demo"}},
    )


def test_generic_update_is_delegated_to_pinned_git_tool(tmp_path, monkeypatch):
    tool = tmp_path / "tools" / "tool.git-project" / "git-project.sh"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    calls = []
    monkeypatch.setattr(repository.os, "name", "posix")
    monkeypatch.setattr(
        repository,
        "run_checked",
        lambda argv, cwd=None: calls.append((argv, cwd)),
    )

    repository.run_generic_repository_command(_context(tmp_path), "update")

    assert calls == [
        (
            ["bash", str(tool), "update", "--repo", str(tmp_path)],
            tmp_path,
        )
    ]


def test_repo_update_runs_generic_update_before_scad_workflow_sync(tmp_path, monkeypatch):
    events = []
    context = _context(tmp_path)
    monkeypatch.setattr(
        repository,
        "run_generic_repository_command",
        lambda ctx, command: events.append(("generic", command)),
    )
    monkeypatch.setattr(
        repository,
        "sync_workflow_refs",
        lambda ctx: events.append(("scad", "workflow-sync")) or [],
    )

    repository.repo_update(context)

    assert events == [("generic", "update"), ("scad", "workflow-sync")]


def test_workflow_sync_uses_configured_semantic_tool_ref(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "ci.yml"
    workflow.write_text(
        """jobs:
  build:
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-build.yml@old
  verify:
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-verify.yml@old
  ci:
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-ci.yml@old
  release:
    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-release.yml@old
""",
        encoding="utf-8",
    )

    ref = f"v{__version__}"
    changed = repository.sync_workflow_refs(_context(tmp_path, tool_ref=ref))
    text = workflow.read_text(encoding="utf-8")

    assert changed == [workflow]
    for name in (
        "reusable-build",
        "reusable-verify",
        "reusable-ci",
        "reusable-release",
    ):
        assert f"{name}.yml@{ref}" in text
    assert "@old" not in text


def test_workflow_sync_preserves_explicit_development_ref(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "ci.yml"
    workflow.write_text(
        "jobs:\n  scad:\n    uses: brainboxemb/tool.scad-project/.github/workflows/reusable-ci.yml@old\n",
        encoding="utf-8",
    )

    repository.sync_workflow_refs(_context(tmp_path, tool_ref="feature/test-release"))

    assert "reusable-ci.yml@feature/test-release" in workflow.read_text(
        encoding="utf-8"
    )
