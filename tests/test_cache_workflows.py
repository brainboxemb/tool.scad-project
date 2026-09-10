from pathlib import Path


BUILD_INPUT_PATTERNS = (
    "dsg/**/*.scad",
    "dsg/**/*.py",
    "dsg/**/render.yml",
    "dsg/**/export.yml",
    "dsg/**/*.stl",
    "dsg/**/*.off",
    "dsg/**/*.amf",
    "dsg/**/*.3mf",
    "dsg/**/*.obj",
    "dsg/**/*.dxf",
    "dsg/**/*.svg",
    "dsg/**/*.dat",
    "dsg/**/*.txt",
    "dsg/**/*.png",
)


def test_scons_cache_keys_track_profiles_and_common_import_assets():
    for workflow in (
        Path(".github/workflows/project-build.yml"),
        Path(".github/workflows/project-verify.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        for pattern in BUILD_INPUT_PATTERNS:
            assert f"'{pattern}'" in text, f"{workflow} does not hash {pattern}"


def test_design_cache_tracks_design_tree_and_common_render_assets():
    text = Path(".github/workflows/project-build.yml").read_text(encoding="utf-8")
    assert "'dsg/**/design/**'" in text
    for pattern in BUILD_INPUT_PATTERNS:
        assert f"'{pattern}'" in text
