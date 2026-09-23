"""SCAD post-update ownership and workflow-ref synchronization.

Checks:
The SCAD post-update hooks remain native/Python-free and own only reusable
SCAD workflow-ref synchronization. Generic bootstrap/update/status behavior
continues to be delegated to the pinned tool.git-project implementation by the
Python compatibility bridge.

Testing approach:
Inspect both platform hooks for the ownership boundary, execute the real shell
hook against a temporary consumer, and inspect the Python repository bridge.
"""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
POST_UPDATE_HOOKS = (
    ROOT / "consumer" / "post-update.sh",
    ROOT / "consumer" / "post-update.ps1",
)
REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-production",
    "project-release",
)


def _write_consumer(tmp_path: Path, ref: str = "v0.15.11") -> Path:
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
    uses: brainboxemb/tool.scad-project/.github/workflows/project-production.yml@v0.15.10
""",
        encoding="utf-8",
    )
    return workflow


def test_post_update_hooks_are_scad_only_and_python_free():
    for path in POST_UPDATE_HOOKS:
        text = path.read_text(encoding="utf-8")
        assert "tools/tool.git-project" not in text
        assert "python" not in text.lower()
        assert "tool.scad-project" in text
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text


def test_shell_post_update_hook_synchronizes_workflow_ref(tmp_path):
    workflow = _write_consumer(tmp_path)

    result = subprocess.run(
        ["bash", str(ROOT / "consumer" / "post-update.sh"), "--repo", str(tmp_path)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "project-production.yml@v0.15.11" in workflow.read_text(encoding="utf-8")
    assert "SCAD post-update synchronization complete." in result.stdout


def test_repository_bridge_delegates_generic_operations_to_tool_git_project():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    assert "tools/tool.git-project" in text
    assert 'run_generic_repository_command(context, "bootstrap")' in text
    assert 'run_generic_repository_command(context, "update")' in text
    assert 'run_generic_repository_command(context, "status")' in text


def test_python_cli_workflow_sync_covers_all_reusable_project_workflows():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    for workflow in REUSABLE_PROJECT_WORKFLOWS:
        assert workflow in text
