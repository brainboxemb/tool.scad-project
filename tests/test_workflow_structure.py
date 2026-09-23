"""Maintained GitHub workflow naming and orientation contract."""

from pathlib import Path


WORKFLOW_DIR = Path(".github/workflows")

EXPECTED = {
    "reusable-build.yml": ("reusable Build", "public reusable workflow API"),
    "reusable-ci.yml": ("reusable CI", "public reusable workflow API"),
    "reusable-release.yml": ("reusable Release", "public reusable workflow API"),
    "reusable-verify.yml": ("reusable Verify", "public reusable workflow API"),
    "self-pages.yml": ("Pages", "repository self-entry workflow"),
    "self-release.yml": ("Release", "repository self-entry workflow"),
    "test-self.yml": ("test Self", "repository qualification workflow"),
}


def test_workflow_files_follow_shared_scope_and_capability_vocabulary():
    actual = {path.name for path in WORKFLOW_DIR.glob("*.yml")}
    assert actual == set(EXPECTED)
    assert not any("production" in name for name in actual)
    assert not any(name.startswith("project-") for name in actual)


def test_workflows_have_compact_display_names_and_purpose_scope_headers():
    for filename, (display_name, scope_text) in EXPECTED.items():
        lines = (WORKFLOW_DIR / filename).read_text(encoding="utf-8").splitlines()
        assert lines[0] == f"name: {display_name}"
        assert lines[2].startswith("# Purpose:")
        assert lines[3].startswith("# Scope:")
        assert scope_text in lines[3]
