"""Tooling and workflow consistency

Checks:
The package version and reusable workflow version markers stay aligned, pinned tool
versions are checked correctly, Build remains the only writer of the shared SCons cache,
cache names/summaries stay understandable, pull-request publication stays isolated and
self-cleaning, workflow helper code uses the available `python3` command, and agreed
job/step timeouts are not accidentally increased.

Testing approach:
Configuration-level tests call the real tooling validator with controlled environment
values. Workflow-policy tests read the YAML files and inspect the relevant actions,
cache keys and timeout values. Where environment variables must be changed for one case,
pytest's `monkeypatch` fixture makes that change temporary and restores the original
environment afterwards.
"""

from pathlib import Path

from scad_project import __version__
from scad_project.config import ProjectContext
from scad_project.tooling import tooling_errors


def context(ref=None):
    if ref is None:
        ref = f"v{__version__}"
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

    package_version = tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]

    assert __version__ == package_version

    for workflow_path in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
        Path(".github/workflows/project-pr-cleanup.yml"),
    ):
        text = workflow_path.read_text(encoding="utf-8")
        match = re.search(
            r"SCAD_PROJECT_WORKFLOW_VERSION:\s*v([0-9]+\.[0-9]+\.[0-9]+)",
            text,
        )
        assert match, f"Missing workflow version marker in {workflow_path}"
        assert match.group(1) == package_version


def test_scons_cache_writer_policy():
    """Keep Build as the only shared SCons cache writer; Verify is restore-only."""
    import yaml

    build = yaml.safe_load(
        Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    )
    verify = yaml.safe_load(
        Path(".github/workflows/project-verify.yml").read_text(encoding="utf-8")
    )

    build_steps = {step["name"]: step for step in build["jobs"]["build"]["steps"]}
    verify_steps = {step["name"]: step for step in verify["jobs"]["verify"]["steps"]}

    assert (
        build_steps["Restore selective build cache"]["uses"]
        == "actions/cache/restore@v4"
    )
    assert build_steps["Save selective build cache"]["uses"] == "actions/cache/save@v4"
    assert (
        verify_steps["Restore selective build cache"]["uses"]
        == "actions/cache/restore@v4"
    )
    assert "Save selective build cache" not in verify_steps


def test_cache_workflow_is_human_readable():
    """Preserve semantic cache names and summaries instead of opaque hash-only UI."""
    import yaml

    build = yaml.safe_load(
        Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    )
    verify = yaml.safe_load(
        Path(".github/workflows/project-verify.yml").read_text(encoding="utf-8")
    )

    build_steps = {step["name"]: step for step in build["jobs"]["build"]["steps"]}
    verify_steps = {step["name"]: step for step in verify["jobs"]["verify"]["steps"]}

    selective_key = build_steps["Restore selective build cache"]["with"]["key"]
    design_key = build_steps["Restore exact generated design snapshot"]["with"]["key"]
    verify_key = verify_steps["Restore selective build cache"]["with"]["key"]

    assert selective_key.startswith("scad-selective-build-v2-")
    assert design_key.startswith("scad-design-snapshot-v2-")
    assert verify_key.startswith("scad-selective-build-v2-")
    assert "Describe build caches" in build_steps
    assert "Summarise cache status" in build_steps
    assert "Summarise selective rebuild result" in build_steps
    assert "Describe selective build cache" in verify_steps
    assert "Summarise cache status" in verify_steps


def test_cache_summary_uses_available_python3_runtime():
    """Prevent the workflow regression where summary generation called absent `python`."""
    text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    assert "python3 - <<'PY'" in text
    assert "\n          python - <<'PY'" not in text


def test_pull_request_publication_workflow_policy():
    """Keep PR previews isolated and avoid write attempts from fork pull requests."""
    build_text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    verify_text = Path(".github/workflows/project-verify.yml").read_text(encoding="utf-8")
    cleanup_text = Path(".github/workflows/project-pr-cleanup.yml").read_text(
        encoding="utf-8"
    )

    for text in (build_text, verify_text):
        assert "SCAD_PROJECT_PR_NUMBER:" in text
        assert "github.event.pull_request.number" in text
        assert "github.event.pull_request.head.repo.full_name == github.repository" in text
        assert "github.event_name != 'pull_request'" in text

    assert "pr_branch_prefix:" in cleanup_text
    assert "default: dev/pr" in cleanup_text
    assert "${PREFIX}-${PR_NUMBER}/${KIND}" in cleanup_text
    assert "git push origin --delete" in cleanup_text
    assert "github.event.pull_request.merged == true" in cleanup_text
    assert "tools/tool.scad-project" not in cleanup_text
    assert "pip install" not in cleanup_text


def test_workflow_timeouts_are_bounded():
    """Keep every reusable/tool CI job and expensive step within the agreed limits."""
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
        ".github/workflows/project-pr-cleanup.yml": {
            "job": ("cleanup", 5),
            "steps": {
                "Checkout repository for authenticated branch cleanup": 2,
                "Configure publication credentials": 2,
                "Remove generated pull request publication branches": 2,
                "Delete merged source branch": 2,
            },
        },
        ".github/workflows/test.yml": {
            "job": ("test", 15),
            "steps": {
                "Checkout": 2,
                "Unit tests": 5,
                "Generate unit-test documentation": 2,
                "Upload unit-test documentation": 2,
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
