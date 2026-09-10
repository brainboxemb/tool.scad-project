from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.index import write_build_index, write_png_index


def context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={
            "paths": {"build_root": "bld"},
            "publication": {
                "production": {
                    "source_branch": "main",
                    "build_branch": "prod/build",
                },
                "release": {"branch_prefix": "rel", "tag_pattern": "v*"},
            },
        },
    )


def test_build_index_links_only_existing_sections(tmp_path: Path):
    (tmp_path / "bld/design").mkdir(parents=True)
    (tmp_path / "bld/png").mkdir(parents=True)

    output = write_build_index(context(tmp_path))
    text = output.read_text(encoding="utf-8")
    assert "Design documentation" in text
    assert "[PNG renders](png/README.md)" in text
    assert "STL exports" not in text
    assert (tmp_path / "bld/png/README.md").is_file()


def test_png_index_lists_generated_images_deterministically(tmp_path: Path):
    png_root = tmp_path / "bld/png"
    nested = png_root / "detail"
    nested.mkdir(parents=True)
    (png_root / "rear-angled.png").write_bytes(b"png")
    (png_root / "front.png").write_bytes(b"png")
    (nested / "middle-coupler.png").write_bytes(b"png")

    output = write_png_index(png_root)
    text = output.read_text(encoding="utf-8")

    assert "![Front](front.png)" in text
    assert "![Rear Angled](rear-angled.png)" in text
    assert "![Detail / Middle Coupler](detail/middle-coupler.png)" in text
    assert text.index("## Detail / Middle Coupler") < text.index("## Front")
    assert text.index("## Front") < text.index("## Rear Angled")


def test_png_index_handles_empty_directory(tmp_path: Path):
    png_root = tmp_path / "bld/png"

    output = write_png_index(png_root)
    text = output.read_text(encoding="utf-8")

    assert output == png_root / "README.md"
    assert "No PNG renders are present." in text


def test_build_index_describes_mutable_production_branch(tmp_path: Path, monkeypatch):
    (tmp_path / "bld").mkdir(parents=True)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF_TYPE", "branch")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    output = write_build_index(context(tmp_path))
    text = output.read_text(encoding="utf-8")

    assert "Context: `production`" in text
    assert "Generated branch: `prod/build`" in text
    assert "mutable snapshot" in text
    assert "\nbuild\n    generated" not in text


def test_build_index_describes_immutable_release_branch(tmp_path: Path, monkeypatch):
    (tmp_path / "bld").mkdir(parents=True)
    monkeypatch.setenv("SCAD_PROJECT_RELEASE_VERSION", "v0.1.0")

    output = write_build_index(context(tmp_path))
    text = output.read_text(encoding="utf-8")

    assert "Context: `release`" in text
    assert "Source: tag `v0.1.0`" in text
    assert "Generated branch: `rel/v0.1.0/build`" in text
    assert "immutable release snapshot" in text
