from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.externals import configured_externals, validate_externals_config


def context(tmp_path: Path, config):
    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def test_external_schema(tmp_path: Path):
    ctx = context(
        tmp_path,
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [
                {
                    "name": "lib.scad.clamps",
                    "type": "git-submodule",
                    "url": "https://github.com/brainboxemb/lib.scad.clamps.git",
                    "path": "dsg/openscad/ext/lib.scad.clamps",
                    "required_file": "openscad/tube-clamp/tube_clamp.scad",
                }
            ],
        },
    )

    externals = configured_externals(ctx)
    assert len(externals) == 1
    assert externals[0].name == "lib.scad.clamps"
    assert validate_externals_config(ctx) == []


def test_legacy_libraries_are_accepted(tmp_path: Path):
    ctx = context(
        tmp_path,
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "libraries": [
                {
                    "name": "legacy",
                    "url": "https://example.invalid/legacy.git",
                    "path": "dsg/openscad/ext/legacy",
                }
            ],
        },
    )

    assert configured_externals(ctx)[0].name == "legacy"
