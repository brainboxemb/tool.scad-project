"""Build engine configuration

Checks:
The `build_engine` section is optional. When present, `direct` and `scons` are accepted,
while the wrong data type or an unknown engine name produces the expected validation
error.

Testing approach:
Each test creates only the small configuration fragment needed for that case and calls
the real configuration validator. The returned error list is compared with the expected
result; no files, renderers or external processes are involved.
"""

from pathlib import Path

from scad_project.build_engine_config import validate_build_engine_config
from scad_project.config import ProjectContext


def _context(tmp_path: Path, value) -> ProjectContext:
    config = {
        "project": {"name": "demo"},
        "paths": {"design_root": "dsg", "build_root": "bld"},
        "externals": [],
    }
    if value is not None:
        config["build_engine"] = value
    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def test_build_engine_config_is_optional(tmp_path):
    assert validate_build_engine_config(_context(tmp_path, None)) == []


def test_build_engine_config_accepts_direct_and_scons(tmp_path):
    assert validate_build_engine_config(
        _context(tmp_path, {"engine": "direct"})
    ) == []
    assert validate_build_engine_config(
        _context(tmp_path, {"engine": "scons"})
    ) == []


def test_build_engine_config_requires_mapping(tmp_path):
    assert validate_build_engine_config(_context(tmp_path, "scons")) == [
        "build_engine must be a mapping"
    ]


def test_build_engine_config_rejects_unknown_engine(tmp_path):
    assert validate_build_engine_config(
        _context(tmp_path, {"engine": "sconz"})
    ) == ["build_engine.engine must be 'direct' or 'scons'"]
