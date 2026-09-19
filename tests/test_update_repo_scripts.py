"""Python-free SCAD consumer update wrappers.

Checks:
Consumer update launchers delegate generic dependency movement directly to the
pinned tool.git-project shell implementation and keep only the SCAD-specific
workflow-ref alignment locally. Basic repository update must not require the
Python-based scad-project CLI.

Testing approach:
Policy checks inspect both canonical updater copies. A shell integration test
executes the real updater against a temporary Git consumer with a fake generic
tool, proving dependency delegation and semantic workflow-ref synchronization
without invoking Python.
"""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

CONSUMER_UPDATERS = (
    ROOT / "consumer" / "update-repo.ps1",
    ROOT / "consumer" / "update-repo.sh",
    ROOT / "bootstrap" / "consumer-update.ps1",
    ROOT / "bootstrap" / "consumer-update.sh",
)

REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-production",
    "project-release",
)


def test_consumer_updaters_are_python_free_git_tool_wrappers():
    for script in CONSUMER_UPDATERS:
        text = script.read_text(encoding="utf-8")
        assert "tools/tool.git-project" in text
        assert "tool.scad-project/scad-project" not in text
        assert "python" not in text.lower()
        assert "submodule add" not in text
        assert "resolve_ref" not in text
        assert "latest_tag" not in text
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text


def test_shell_updater_delegates_and_synchronizes_workflow_ref(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True, text=True)

    generic_tool = tmp_path / "tools" / "tool.git-project" / "git-project.sh"
    generic_tool.parent.mkdir(parents=True)
    generic_tool.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" > "$3/generic-update.args"
""",
        encoding="utf-8",
    )
    generic_tool.chmod(generic_tool.stat().st_mode | 0o111)

    (tmp_path / "project.yml").write_text(
        """schema_version: 1
project:
  name: demo
profiles:
  - type: scad
    config: project.scad.yml
dependencies:
  - name: tool.scad-project
    role: tooling
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v0.15.1
""",
        encoding="utf-8",
    )
    (tmp_path / "project.scad.yml").write_text(
        "paths:\n  design_root: .\n  build_root: bld\n",
        encoding="utf-8",
    )
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    workflow = workflows / "scad.yml"
    workflow.write_text(
        """jobs:
  scad:
    uses: brainboxemb/tool.scad-project/.github/workflows/project-production.yml@v0.15.0
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(ROOT / "consumer" / "update-repo.sh")],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "update --repo" in (tmp_path / "generic-update.args").read_text(encoding="utf-8")
    assert "project-production.yml@v0.15.1" in workflow.read_text(encoding="utf-8")
    assert "SCAD repository update complete." in result.stdout


def test_repository_bridge_still_delegates_cli_compatibility_to_tool_git_project():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    assert "tools/tool.git-project" in text
    assert 'run_generic_repository_command(context, "update")' in text
    assert 'run_generic_repository_command(context, "bootstrap")' in text


def test_python_cli_workflow_sync_covers_all_reusable_project_workflows():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    for workflow in REUSABLE_PROJECT_WORKFLOWS:
        assert workflow in text


def test_python_cli_workflow_sync_uses_configured_tool_ref_not_checked_out_sha():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    assert "configured_scad_tool_ref" in text
    assert 'tool.get("ref")' in text
    assert "@{tool_ref}" in text
    assert '"rev-parse", "HEAD"' not in text
    assert "tool_sha" not in text
