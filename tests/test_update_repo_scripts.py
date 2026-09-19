"""Python-free SCAD consumer update wrappers."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

CONSUMER_UPDATERS = (
    ROOT / "consumer" / "update-repo.ps1",
    ROOT / "consumer" / "update-repo.sh",
)
BOOTSTRAP_UPDATERS = (
    ROOT / "bootstrap" / "consumer-update.ps1",
    ROOT / "bootstrap" / "consumer-update.sh",
)
REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-production",
    "project-release",
)


def test_consumer_updaters_are_python_free_native_composition_wrappers():
    for script in (*CONSUMER_UPDATERS, *BOOTSTRAP_UPDATERS):
        text = script.read_text(encoding="utf-8")
        assert "tool.git-project" in text
        assert "tool.scad-project/scad-project" not in text
        assert "python" not in text.lower()
        assert "repo-update" not in text
        assert "submodule add" not in text
        assert "submodule update" not in text
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text


def test_bootstrap_and_consumer_update_scripts_stay_identical():
    assert BOOTSTRAP_UPDATERS[0].read_text(encoding="utf-8") == CONSUMER_UPDATERS[0].read_text(encoding="utf-8")
    assert BOOTSTRAP_UPDATERS[1].read_text(encoding="utf-8") == CONSUMER_UPDATERS[1].read_text(encoding="utf-8")


def test_posix_consumer_update_runs_without_scad_python_cli(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    (tmp_path / "project.scad.yml").write_text("paths:\n  build_root: bld\n", encoding="utf-8")
    (tmp_path / "project.yml").write_text(
        """schema_version: 1

project:
  name: fixture

profiles:
  - type: scad
    config: project.scad.yml

dependencies:
  - name: tool.scad-project
    role: tooling
    type: git-submodule
    url: https://example.invalid/tool.scad-project.git
    path: tools/tool.scad-project
    ref: v9.8.7
""",
        encoding="utf-8",
    )

    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "scad.yml"
    workflow.write_text(
        "jobs:\n  scad:\n    uses: brainboxemb/tool.scad-project/.github/workflows/project-production.yml@old\n",
        encoding="utf-8",
    )

    git_tool = tmp_path / "tools" / "tool.git-project" / "git-project.sh"
    git_tool.parent.mkdir(parents=True)
    git_tool.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho native-update > \"$(git rev-parse --show-toplevel)/native-update.txt\"\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", str(ROOT / "consumer" / "update-repo.sh")],
        cwd=tmp_path,
        check=True,
    )

    assert (tmp_path / "native-update.txt").read_text(encoding="utf-8").strip() == "native-update"
    assert "project-production.yml@v9.8.7" in workflow.read_text(encoding="utf-8")


def test_repository_bridge_still_delegates_python_cli_compatibility_commands():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    assert "tools/tool.git-project" in text
    assert 'run_generic_repository_command(context, "update")' in text
    assert 'run_generic_repository_command(context, "bootstrap")' in text


def test_python_workflow_sync_still_uses_configured_tool_ref():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(encoding="utf-8")
    assert "configured_scad_tool_ref" in text
    assert 'tool.get("ref")' in text
    assert "@{tool_ref}" in text
