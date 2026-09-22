"""Python-free SCAD post-update composition contract."""

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-production",
    "project-release",
)


def _write_consumer(tmp_path: Path, ref: str = "v0.15.1") -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True, text=True)
    (tmp_path / "project.yml").write_text(
        f"""schema_version: 1
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
    ref: {ref}
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
    return workflow


def test_shell_post_update_hook_synchronizes_workflow_ref(tmp_path):
    workflow = _write_consumer(tmp_path)

    result = subprocess.run(
        ["bash", str(ROOT / "consumer" / "post-update.sh"), "--repo", str(tmp_path)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "project-production.yml@v0.15.1" in workflow.read_text(encoding="utf-8")
    assert "SCAD post-update synchronization complete." in result.stdout


def test_compatibility_shell_updater_composes_generic_update_and_scad_hook(tmp_path):
    workflow = _write_consumer(tmp_path)

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

    scad_consumer = tmp_path / "tools" / "tool.scad-project" / "consumer"
    scad_consumer.mkdir(parents=True)
    hook = scad_consumer / "post-update.sh"
    shutil.copy2(ROOT / "consumer" / "post-update.sh", hook)
    hook.chmod(hook.stat().st_mode | 0o111)

    result = subprocess.run(
        ["bash", str(ROOT / "consumer" / "update-repo.sh")],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "update --repo" in (tmp_path / "generic-update.args").read_text(encoding="utf-8")
    assert "project-production.yml@v0.15.1" in workflow.read_text(encoding="utf-8")
    assert "SCAD post-update synchronization complete." in result.stdout


def test_compatibility_shell_status_does_not_run_post_update_hook(tmp_path):
    workflow = _write_consumer(tmp_path)

    generic_tool = tmp_path / "tools" / "tool.git-project" / "git-project.sh"
    generic_tool.parent.mkdir(parents=True)
    generic_tool.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" > "$3/generic-status.args"
""",
        encoding="utf-8",
    )
    generic_tool.chmod(generic_tool.stat().st_mode | 0o111)

    scad_consumer = tmp_path / "tools" / "tool.scad-project" / "consumer"
    scad_consumer.mkdir(parents=True)
    hook = scad_consumer / "post-update.sh"
    hook.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
touch "$2/hook-ran"
""",
        encoding="utf-8",
    )
    hook.chmod(hook.stat().st_mode | 0o111)

    subprocess.run(
        ["bash", str(ROOT / "consumer" / "update-repo.sh"), "status"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "status --repo" in (tmp_path / "generic-status.args").read_text(encoding="utf-8")
    assert not (tmp_path / "hook-ran").exists()
    assert "project-production.yml@v0.15.0" in workflow.read_text(encoding="utf-8")


def test_repository_bridge_still_delegates_cli_compatibility_to_tool_git_project():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    assert "tools/tool.git-project" in text
    assert 'run_generic_repository_command(context, "update")' in text
    assert 'run_generic_repository_command(context, "bootstrap")' in text


def test_python_cli_workflow_sync_covers_all_reusable_project_workflows():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    for workflow in REUSABLE_PROJECT_WORKFLOWS:
        assert workflow in text
