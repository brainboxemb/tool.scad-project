"""SCAD consumer repository update wrappers

Checks:
The consumer update launchers stay thin: they invoke the local `tool.scad-project`
`repo-update` compatibility command and do not reimplement Git dependency parsing,
submodule registration or ref resolution. That command delegates generic repository
work to the pinned `tool.git-project` and then synchronizes SCAD workflow callers.

Testing approach:
The tests inspect the shell and PowerShell launcher text. They require the expected
SCAD command and reject implementation markers from the removed generic dependency
manager.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "bootstrap" / "consumer-update.sh",
    ROOT / "bootstrap" / "consumer-update.ps1",
)


def test_consumer_updaters_delegate_to_scad_repo_update():
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert "repo-update" in text
        assert "tools/tool.scad-project" in text


def test_consumer_updaters_do_not_reimplement_generic_git_management():
    forbidden = (
        "submodule add",
        "fetch --prune --tags",
        "latest_tag",
        "Resolve-DependencyRef",
        "tool_scad_project:",
        "externals:",
    )
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path} contains generic Git logic: {marker}"
