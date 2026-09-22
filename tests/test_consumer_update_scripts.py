"""Canonical SCAD consumer repository update launchers.

Checks:
The bootstrap launchers keep basic dependency update Python-free by invoking the
pinned native tool.git-project scripts directly. They retain only the
SCAD-specific reusable-workflow ref synchronization needed after dependency
movement.

Testing approach:
Inspect the canonical bootstrap shell and PowerShell launchers and reject the
old Python scad-project compatibility path plus generic Git implementation
details that belong to tool.git-project.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "bootstrap" / "consumer-update.sh",
    ROOT / "bootstrap" / "consumer-update.ps1",
)


def test_consumer_updaters_delegate_directly_to_git_tool_without_python():
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert "tools/tool.git-project" in text
        assert "tool.scad-project/scad-project" not in text
        assert "repo-update" not in text
        assert "python" not in text.lower()


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


def test_consumer_updaters_preserve_update_and_status_modes():
    shell = (ROOT / "bootstrap" / "consumer-update.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "bootstrap" / "consumer-update.ps1").read_text(encoding="utf-8")

    assert 'mode="${1:-update}"' in shell
    assert 'update|status' in shell
    assert 'bash "$git_tool" "$mode" --repo "$root"' in shell
    assert 'if [[ "$mode" == "status" ]]' in shell

    assert '[ValidateSet("update", "status")]' in powershell
    assert '[string] $Mode = "update"' in powershell
    assert '& $GitTool $Mode -RepoRoot $Root' in powershell
    assert 'if ($Mode -eq "status")' in powershell
