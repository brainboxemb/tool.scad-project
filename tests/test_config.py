"""Project configuration

Checks:
A minimal project configuration is valid, supported publication and watermark settings
are accepted, and invalid types or empty values are rejected with useful messages.
Render and export directory settings are also checked.

Testing approach:
The tests construct small Python dictionaries that represent `project.yml` variants and
pass them to the real project validator. Each case checks either an empty error list or
the specific validation messages expected for bad input.
"""

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


def test_watermark_config(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [],
            "builds": [],
            "rendering": {
                "watermark": {
                    "text": "© 2026 brainboxemb",
                }
            },
        },
    )
    assert validate_config(ctx) == []


def test_watermark_config_rejects_empty_text(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path, tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg/openscad", "build_root": "bld"},
            "externals": [],
            "builds": [],
            "rendering": {"watermark": {"text": ""}},
        },
    )
    assert (
        "rendering.watermark.text must be a non-empty string"
        in validate_config(ctx)
    )


def test_directory_build_paths_are_valid(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "dsg/openscad/render",
                "export_root": "dsg/openscad/export",
            },
            "externals": [],
        },
    )
    assert validate_config(ctx) == []


def test_directory_build_paths_reject_empty_values(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "",
                "export_root": [],
            },
            "externals": [],
        },
    )
    errors = validate_config(ctx)
    assert "paths.render_root must be a non-empty path string" in errors
    assert "paths.export_root must be a non-empty path string" in errors
