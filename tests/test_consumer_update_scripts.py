"""SCAD repository update compatibility and post-update hook policy."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPAT_UPDATERS = (
    ROOT / "bootstrap" / "consumer-update.sh",
    ROOT / "bootstrap" / "consumer-update.ps1",
    ROOT / "consumer" / "update-repo.sh",
    ROOT / "consumer" / "update-repo.ps1",
)
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


def test_compatibility_updaters_delegate_generic_repository_operation():
    for path in COMPAT_UPDATERS:
        text = path.read_text(encoding="utf-8")
        assert "tools/tool.git-project" in text
        assert "consumer/post-update" in text
        assert "python" not in text.lower()
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow not in text


def test_compatibility_updaters_preserve_read_only_status():
    shell = (ROOT / "consumer" / "update-repo.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "consumer" / "update-repo.ps1").read_text(encoding="utf-8")

    assert 'mode="${1:-update}"' in shell
    assert 'update|status' in shell
    assert 'bash "$git_tool" "$mode" --repo "$root"' in shell
    assert '[[ "$mode" == "status" ]] && exit 0' in shell

    assert '[ValidateSet("update", "status")]' in powershell
    assert '[string] $Mode = "update"' in powershell
    assert '& $GitTool $Mode -RepoRoot $Root' in powershell
    assert 'if ($Mode -eq "status")' in powershell


def test_post_update_hooks_are_scad_only_and_python_free():
    for path in POST_UPDATE_HOOKS:
        text = path.read_text(encoding="utf-8")
        assert "tools/tool.git-project" not in text
        assert "python" not in text.lower()
        assert "tool.scad-project" in text
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text
