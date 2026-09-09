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


def test_publication_policy_config(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [],
            "builds": [],
            "publication": {
                "production": {
                    "source_branch": "main",
                    "build_branch": "build",
                    "verification_branch": "verification",
                },
                "development": {
                    "build_branch": "dev/build",
                    "verification_branch": "dev/verification",
                },
                "tags": {"pattern": "v*"},
            },
        },
    )
    assert validate_config(ctx) == []


def test_publication_policy_rejects_wrong_types(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [],
            "builds": [],
            "publication": {
                "production": {"source_branch": 123},
                "development": {"build_branch": []},
                "tags": {"pattern": 42},
            },
        },
    )
    errors = validate_config(ctx)
    assert "publication.production.source_branch must be a string" in errors
    assert "publication.development.build_branch must be a string" in errors
    assert "publication.tags.pattern must be a string" in errors
