"""Build cache inputs

Checks:
GitHub Actions cache keys include every project input that can change generated CAD
output: OpenSCAD and Python source, render/export profiles, design metadata, and
commonly imported asset formats. Cache hashing must work for any configured project
layout rather than assuming that design source always lives under ``dsg/``.

Testing approach:
These tests read the reusable Build and Verify workflow YAML as text and check for the
required repository-wide file patterns in the cache hash expressions. GitHub Actions
itself is not started; the workflow definition is the configuration being verified.
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


def test_cache_globs_are_layout_independent():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        assert "dsg/**" not in text, f"{workflow} hard-codes the dsg source layout"
        assert "'**/*.scad'" in text


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
