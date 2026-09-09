from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.tooling import tooling_errors


def context(ref="v0.6.1"):
    return ProjectContext(
        root=Path("."),
        config_file=Path("project.yml"),
        config={
            "tooling": {
                "tool_scad_project": {
                    "type": "git-submodule",
                    "url": "https://github.com/brainboxemb/tool.scad-project.git",
                    "path": "tools/tool.scad-project",
                    "ref": ref,
                }
            }
        },
    )


def test_exact_tooling_tag_matches_running_version(monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    assert tooling_errors(context()) == []


def test_exact_tag_detects_workflow_mismatch(monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "v9.9.9")
    errors = tooling_errors(context())
    assert any("workflow" in error for error in errors)


def test_floating_main_does_not_require_package_version_match(monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "v0.4.2")
    assert tooling_errors(context("main")) == []


def test_latest_does_not_require_package_version_match(monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "v0.4.2")
    assert tooling_errors(context("latest")) == []


def test_tooling_requires_ref(monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    ctx = ProjectContext(
        Path("."),
        Path("project.yml"),
        config={"tooling": {"tool_scad_project": {}}},
    )
    assert tooling_errors(ctx) == ["Missing tooling tool.scad-project ref"]
