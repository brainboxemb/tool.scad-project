from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.tooling import tooling_errors


def context(version="v0.4.1"):
    return ProjectContext(
        root=Path("."),
        config_file=Path("project.yml"),
        config={"tooling": {"tool_scad_project_version": version}},
    )


def test_tooling_matches_running_version(monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    assert tooling_errors(context()) == []


def test_tooling_detects_workflow_mismatch(monkeypatch):
    monkeypatch.setenv("SCAD_PROJECT_WORKFLOW_VERSION", "v9.9.9")
    errors = tooling_errors(context())
    assert any("workflow" in error for error in errors)


def test_tooling_requires_project_version(monkeypatch):
    monkeypatch.delenv("SCAD_PROJECT_WORKFLOW_VERSION", raising=False)
    ctx = ProjectContext(Path("."), Path("project.yml"), config={})
    assert tooling_errors(ctx) == [
        "Missing value: tooling.tool_scad_project_version"
    ]
