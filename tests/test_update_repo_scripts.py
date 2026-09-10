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
    for root_script, _bootstrap_script in UPDATER_PAIRS:
        text = root_script.read_text(encoding="utf-8")
        for workflow in REUSABLE_PROJECT_WORKFLOWS:
            assert workflow in text, f"{root_script} does not update {workflow}"
