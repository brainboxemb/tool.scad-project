from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.index import write_build_index


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
    assert "PNG renders" in text
    assert "STL exports" not in text


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
