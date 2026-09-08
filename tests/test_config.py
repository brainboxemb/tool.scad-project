from pathlib import Path
from scad_project.config import ProjectContext, validate_config

def test_minimal_config(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [],
            "builds": [],
        },
    )
    assert validate_config(ctx) == []
