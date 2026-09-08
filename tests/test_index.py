from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.index import write_build_index


def test_build_index_links_only_existing_sections(tmp_path: Path):
    (tmp_path / "bld/design").mkdir(parents=True)
    (tmp_path / "bld/png").mkdir(parents=True)
    ctx = ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={"paths": {"build_root": "bld"}},
    )

    output = write_build_index(ctx)
    text = output.read_text(encoding="utf-8")
    assert "Design documentation" in text
    assert "PNG renders" in text
    assert "STL exports" not in text
