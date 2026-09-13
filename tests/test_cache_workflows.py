"""Build/verification cache inputs and telemetry context

Checks:
GitHub Actions cache keys include every project input that can change generated CAD
output: generic and SCAD profile configuration, OpenSCAD and Python source,
render/export profiles, design metadata, and commonly imported asset formats. Cache
hashing must work for any configured project layout rather than assuming that design
source always lives under ``dsg/``. Verify restores the normal build cache read-only
and owns a separate writable cache for verification-only targets. Reusable workflows
also expose exact tool/cache context and summarize the four structured target outcomes.

Testing approach:
These tests read the reusable Build and Verify workflow YAML as text and check for the
required repository-wide file patterns, cache namespaces, provenance environment
variables and structured outcome vocabulary. GitHub Actions itself is not started;
Actions-level exact/fallback/miss qualification remains Step 5.
"""

from pathlib import Path


BUILD_INPUT_PATTERNS = (
    "**/*.scad",
    "**/*.py",
    "**/render.yml",
    "**/export.yml",
    "**/*.stl",
    "**/*.off",
    "**/*.amf",
    "**/*.3mf",
    "**/*.obj",
    "**/*.dxf",
    "**/*.svg",
    "**/*.dat",
    "**/*.txt",
    "**/*.png",
)

TELEMETRY_ENV = (
    "SCAD_PROJECT_TOOL_SHA",
    "SCAD_PROJECT_CACHE_NAMESPACE",
    "SCAD_PROJECT_CACHE_PRIMARY_KEY",
    "SCAD_PROJECT_CACHE_MATCHED_KEY",
    "SCAD_PROJECT_CACHE_HIT",
)

OUTCOMES = ("BUILT", "CACHE_RESTORED", "CURRENT", "ERROR")


def test_cache_globs_are_layout_independent():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        assert "dsg/**" not in text, f"{workflow} hard-codes the dsg source layout"
        assert "'**/*.scad'" in text


def test_cache_keys_track_generic_and_scad_profile_config():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        assert "'project.yml'" in text
        assert "'project.scad.yml'" in text


def test_scons_cache_keys_track_profiles_and_common_import_assets():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        for pattern in BUILD_INPUT_PATTERNS:
            assert f"'{pattern}'" in text, f"{workflow} does not hash {pattern}"


def test_project_build_scons_cache_tracks_design_metadata():
    text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    scons_cache_block = text.split(
        "- name: Restore exact generated design snapshot",
        1,
    )[0]
    assert "'**/design/**'" in scons_cache_block


def test_design_cache_tracks_design_tree_and_common_render_assets():
    text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    assert "'**/design/**'" in text
    for pattern in BUILD_INPUT_PATTERNS:
        assert f"'{pattern}'" in text


def test_verify_uses_separate_writable_verification_cache():
    text = Path(".github/workflows/project-verify.yml").read_text(encoding="utf-8")

    assert "path: .cache/scad-project/scons" in text
    assert "Verify cache mode: restore-only" in text
    assert "path: .cache/scad-project/verification-scons" in text
    assert "scad-verification-v1-" in text
    assert "- name: Save selective verification cache" in text
    assert "uses: actions/cache/save@v4" in text
    assert ".cache/scad-project/verification-state/last-verification-build.json" in text


def test_reusable_workflows_expose_structured_telemetry_context():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        for variable in TELEMETRY_ENV:
            assert variable in text, f"{workflow} does not expose {variable}"
        for outcome in OUTCOMES:
            assert outcome in text, f"{workflow} does not summarize {outcome}"


def test_build_uploads_normal_and_design_decision_reports():
    text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    assert ".cache/scad-project/state/last-build.json" in text
    assert ".cache/scad-project/state/last-design-build.json" in text


def test_verify_switches_cache_context_and_uploads_both_decision_reports():
    text = Path(".github/workflows/project-verify.yml").read_text(encoding="utf-8")
    assert "SCAD_PROJECT_CACHE_NAMESPACE=scad-selective-build-v2" in text
    assert "SCAD_PROJECT_CACHE_NAMESPACE=scad-verification-v1" in text
    assert ".cache/scad-project/state/last-build.json" in text
    assert ".cache/scad-project/verification-state/last-verification-build.json" in text
