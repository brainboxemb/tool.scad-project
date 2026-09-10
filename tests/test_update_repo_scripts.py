"""Repository updater scripts

Checks:
The root and bootstrap copies of the Bash and PowerShell updater stay identical, an
update changes Build, Verify and Release workflow references together, and reusable
workflow calls are pinned to the exact checked-out `tool.scad-project` commit rather
than an annotated version tag.

Testing approach:
The tests read the updater scripts as files. They compare duplicate script bytes
directly and inspect the script text for the required workflow names and exact-SHA
assignment rules; the updater is not allowed to modify a real consumer repository during
these unit tests.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

UPDATER_PAIRS = (
    (ROOT / "update-repo.ps1", ROOT / "bootstrap" / "update-repo.ps1"),
    (ROOT / "update-repo.sh", ROOT / "bootstrap" / "update-repo.sh"),
)

REUSABLE_PROJECT_WORKFLOWS = (
    "project-build",
    "project-verify",
    "project-release",
)


def test_root_updaters_match_bootstrap_copies():
    for root_script, bootstrap_script in UPDATER_PAIRS:
        assert root_script.read_bytes() == bootstrap_script.read_bytes(), (
            root_script,
            bootstrap_script,
        )


def test_updaters_cover_all_reusable_project_workflows():
    """Prevent Release from lagging behind when Build and Verify are upgraded."""
    for root_script, _bootstrap_script in UPDATER_PAIRS:
        text = root_script.read_text(encoding="utf-8")
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text, f"{root_script} does not update {workflow}"


def test_updaters_pin_workflows_to_checked_out_tool_commit():
    """Keep external reusable workflows on an exact SHA while project.yml stays semantic."""
    bash = (ROOT / "update-repo.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "update-repo.ps1").read_text(encoding="utf-8")

    assert 'tool_workflow_ref="$new"' in bash
    assert 'tool_workflow_ref="$workflow_ref"' not in bash

    assert '$ToolWorkflowRef = $New' in powershell
    assert '$ToolWorkflowRef = $Resolved.WorkflowRef' not in powershell
