"""SCAD consumer update wrappers.

Checks:
Consumer update launchers stay thin: they invoke the SCAD `repo-update` command and do
not contain their own YAML parser, ref resolver or Git-submodule update implementation.
The SCAD repository bridge remains responsible only for invoking `tool.git-project` and
for aligning Build, Verify, Production and Release reusable workflow callers with the
configured `tool.scad-project` ref from project configuration.

Testing approach:
The tests inspect the launcher and bridge source files as text. This is a policy-level
boundary test: generic Git implementation keywords are rejected from the consumer
wrappers while all SCAD reusable workflow names and the configured-ref alignment path
must remain covered by the bridge.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONSUMER_UPDATERS = (
    ROOT / "consumer" / "update-repo.ps1",
    ROOT / "consumer" / "update-repo.sh",
)

REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-production",
    "project-release",
)


def test_consumer_updaters_are_thin_scad_wrappers():
    for script in CONSUMER_UPDATERS:
        text = script.read_text(encoding="utf-8")
        assert "repo-update" in text
        assert "tool.scad-project" in text
        assert "submodule add" not in text
        assert "submodule update" not in text
        assert "resolve_ref" not in text
        assert "latest_tag" not in text
        assert "externals:" not in text


def test_repository_bridge_delegates_to_tool_git_project():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    assert "tools/tool.git-project" in text
    assert 'run_generic_repository_command(context, "update")' in text
    assert 'run_generic_repository_command(context, "bootstrap")' in text


def test_workflow_sync_covers_all_reusable_project_workflows():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    for workflow in REUSABLE_PROJECT_WORKFLOWS:
        assert workflow in text


def test_workflow_sync_uses_configured_tool_ref_not_checked_out_sha():
    text = (ROOT / "src" / "scad_project" / "repository.py").read_text(
        encoding="utf-8"
    )
    assert "configured_scad_tool_ref" in text
    assert 'tool.get("ref")' in text
    assert "@{tool_ref}" in text
    assert '"rev-parse", "HEAD"' not in text
    assert "tool_sha" not in text
