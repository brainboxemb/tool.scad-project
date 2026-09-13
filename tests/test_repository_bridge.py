"""Generic repository-tool delegation

Checks:
Repository bootstrap/status/update operations are delegated to the pinned
`tool.git-project` checkout instead of being reimplemented by the SCAD tool. After a
generic update, SCAD reusable Build, Verify and Release workflow callers are aligned to
the exact checked-out `tool.scad-project` commit.

Testing approach:
Tests create small temporary repository layouts and replace command execution or Git SHA
lookup with deterministic test doubles. They inspect the exact delegated command and the
workflow-file rewrite without contacting GitHub or changing real submodules.
"""

from pathlib import Path
from types import SimpleNamespace

import scad_project.repository as repository
from scad_project.config import ProjectContext


def _context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        tmp_path,
        tmp_path / "project.scad.yml",
        {"project": {"name": "demo"}},
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


def test_workflow_sync_pins_build_verify_and_release_to_checked_out_sha(
    tmp_path, monkeypatch
):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "ci.yml"
    workflow.write_text(
        """jobs:
  build:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-build.yml@old
  verify:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-verify.yml@old
  release:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-release.yml@old
""",
        encoding="utf-8",
    )
    tool_root = tmp_path / "tools" / "tool.scad-project"
    tool_root.mkdir(parents=True)

    sha = "a" * 40
    monkeypatch.setattr(
        repository.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=sha + "\n",
            stderr="",
        ),
    )

    changed = repository.sync_workflow_refs(_context(tmp_path))
    text = workflow.read_text(encoding="utf-8")

    assert changed == [workflow]
    for name in ("project-build", "project-verify", "project-release"):
        assert f"{name}.yml@{sha}" in text
    assert "@old" not in text
