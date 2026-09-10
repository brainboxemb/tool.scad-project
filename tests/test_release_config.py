from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.release_config import validate_release_config


def context(tmp_path: Path, release):
    return ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "publication": {"release": release},
        },
    )


def test_release_config_is_optional(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {"project": {"name": "demo"}, "paths": {"design_root": "dsg", "build_root": "bld"}},
    )
    assert validate_release_config(ctx) == []


def test_release_config_requires_mapping(tmp_path: Path):
    assert validate_release_config(context(tmp_path, "rel")) == [
        "publication.release must be a mapping"
    ]


def test_release_config_accepts_supported_values(tmp_path: Path):
    assert validate_release_config(
        context(
            tmp_path,
            {
                "branch_prefix": "rel",
                "tag_pattern": "v*",
                "changelog": "CHANGELOG.md",
            },
        )
    ) == []


def test_release_config_rejects_blank_or_non_string_values(tmp_path: Path):
    errors = validate_release_config(
        context(
            tmp_path,
            {
                "branch_prefix": " ",
                "tag_pattern": 123,
                "changelog": "",
            },
        )
    )
    assert errors == [
        "publication.release.branch_prefix must be a non-empty string",
        "publication.release.tag_pattern must be a non-empty string",
        "publication.release.changelog must be a non-empty string",
    ]
