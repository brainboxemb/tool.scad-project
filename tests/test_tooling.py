from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.tooling import tooling_errors


def context(ref="v0.9.2"):
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


def test_release_version_markers_are_aligned():
    import re
    import tomllib
    from scad_project import __version__

    package_version = tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]

    assert __version__ == package_version

    for workflow_path in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow_path.read_text(encoding="utf-8")
        match = re.search(
            r"SCAD_PROJECT_WORKFLOW_VERSION:\s*v([0-9]+\.[0-9]+\.[0-9]+)",
            text,
        )
        assert match, f"Missing workflow version marker in {workflow_path}"
        assert match.group(1) == package_version


def test_workflow_timeouts_are_bounded():
    import yaml

    expected = {
        ".github/workflows/project-build.yml": {
            "job": ("build", 15),
            "steps": {
                "Checkout project and pinned submodules": 2,
                "Generate design documentation": 5,
                "Build configured outputs": 5,
                "Upload generated build": 2,
                "Publish generated build branch": 2,
            },
        },
        ".github/workflows/project-verify.yml": {
            "job": ("verify", 15),
            "steps": {
                "Checkout project and pinned submodules": 2,
                "Verify project source and configured builds": 5,
                "Run project functional verification": 5,
                "Upload verification evidence": 2,
                "Publish verification branch": 2,
            },
        },
        ".github/workflows/test.yml": {
            "job": ("test", 15),
            "steps": {
                "Checkout": 2,
                "Unit tests": 5,
            },
        },
        ".github/workflows/release.yml": {
            "job": ("release", 10),
            "steps": {
                "Checkout release workflow ref with full history": 2,
                "Resolve and validate release request": 2,
                "Create annotated release tag": 2,
                "Dispatch tests on released tag": 2,
                "Remove release request branch": 2,
            },
        },
    }

    for workflow_path, policy in expected.items():
        data = yaml.safe_load(Path(workflow_path).read_text(encoding="utf-8"))
        job_name, job_timeout = policy["job"]
        job = data["jobs"][job_name]

        assert job["timeout-minutes"] == job_timeout

        steps = {step["name"]: step for step in job["steps"]}
        for step_name, timeout in policy["steps"].items():
            assert steps[step_name]["timeout-minutes"] == timeout
