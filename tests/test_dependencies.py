from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.dependencies import (
    configured_dependencies,
    validate_dependency_config,
)


def context(tmp_path: Path, config):
    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def test_modern_tooling_and_external_refs(tmp_path: Path):
    ctx = context(
        tmp_path,
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "tooling": {
                "tool_scad_project": {
                    "type": "git-submodule",
                    "url": "https://github.com/brainboxemb/tool.scad-project.git",
                    "path": "tools/tool.scad-project",
                    "ref": "main",
                }
            },
            "externals": [
                {
                    "name": "lib.scad.clamps",
                    "type": "git-submodule",
                    "url": "https://github.com/brainboxemb/lib.scad.clamps.git",
                    "path": "dsg/openscad/ext/lib.scad.clamps",
                    "ref": "latest",
                }
            ],
        },
    )

    deps = configured_dependencies(ctx)
    assert [(d.name, d.ref) for d in deps] == [
        ("tool.scad-project", "main"),
        ("lib.scad.clamps", "latest"),
    ]
    assert validate_dependency_config(ctx) == []


def test_dependency_ref_is_required(tmp_path: Path):
    ctx = context(
        tmp_path,
        {
            "tooling": {
                "tool_scad_project": {
                    "path": "tools/tool.scad-project",
                }
            }
        },
    )
    errors = validate_dependency_config(ctx)
    assert any("ref is required" in error for error in errors)
