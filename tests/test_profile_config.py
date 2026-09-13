"""Generic project plus SCAD profile loading

Checks:
Current-generation consumers can keep generic project/profile/dependency policy in
`project.yml` while SCAD-only settings live in `project.scad.yml`. The SCAD runtime view
uses the generic project name, tool dependency and external dependency locations while
preserving SCAD-only external metadata such as required files. Legacy combined
`project.yml` loading remains available during the migration.

Testing approach:
Tests write small YAML files into a temporary repository and call the real context
loader. They inspect the composed in-memory SCAD configuration and exercise error cases
without cloning dependencies or invoking CAD tools.
"""

from pathlib import Path

import pytest

from scad_project.config import ConfigError, load_context


def test_split_project_and_scad_profile_are_composed(tmp_path: Path):
    (tmp_path / "project.yml").write_text(
        """schema_version: 1
project:
  name: demo
profiles:
  - type: scad
    config: project.scad.yml
dependencies:
  - name: tool.scad-project
    role: tooling
    type: git-submodule
    url: https://github.com/brainboxemb/tool.scad-project.git
    path: tools/tool.scad-project
    ref: 1111111111111111111111111111111111111111
  - name: lib.scad.demo
    role: external
    type: git-submodule
    url: https://example.invalid/lib.scad.demo.git
    path: dsg/openscad/ext/lib.scad.demo
    ref: 2222222222222222222222222222222222222222
""",
        encoding="utf-8",
    )
    (tmp_path / "project.scad.yml").write_text(
        """paths:
  design_root: dsg/openscad
  build_root: bld
externals:
  - name: lib.scad.demo
    required_file: openscad/demo.scad
""",
        encoding="utf-8",
    )

    context = load_context(tmp_path)

    assert context.config_file == tmp_path / "project.scad.yml"
    assert context.repository_config is not None
    assert context.config["project"] == {"name": "demo"}
    assert context.config["tooling"]["tool_scad_project"]["ref"] == "1" * 40
    assert context.config["externals"] == [
        {
            "name": "lib.scad.demo",
            "required_file": "openscad/demo.scad",
            "type": "git-submodule",
            "url": "https://example.invalid/lib.scad.demo.git",
            "path": "dsg/openscad/ext/lib.scad.demo",
            "ref": "2" * 40,
        }
    ]


def test_split_config_rejects_metadata_for_unmanaged_external(tmp_path: Path):
    (tmp_path / "project.yml").write_text(
        """schema_version: 1
project:
  name: demo
profiles:
  - type: scad
    config: project.scad.yml
dependencies:
  - name: managed
    role: external
    type: git-submodule
    url: https://example.invalid/managed.git
    path: dsg/ext/managed
    ref: 2222222222222222222222222222222222222222
""",
        encoding="utf-8",
    )
    (tmp_path / "project.scad.yml").write_text(
        """paths:
  design_root: dsg
  build_root: bld
externals:
  - name: unmanaged
    required_file: demo.scad
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="no matching generic dependency: unmanaged"):
        load_context(tmp_path)


def test_generic_project_requires_scad_profile(tmp_path: Path):
    (tmp_path / "project.yml").write_text(
        """schema_version: 1
project:
  name: demo
profiles:
  - type: java
    config: project.java.yml
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="does not declare a SCAD profile"):
        load_context(tmp_path)


def test_legacy_combined_project_yml_remains_supported(tmp_path: Path):
    (tmp_path / "project.yml").write_text(
        """project:
  name: legacy
paths:
  design_root: dsg
  build_root: bld
externals: []
""",
        encoding="utf-8",
    )

    context = load_context(tmp_path)

    assert context.config_file == tmp_path / "project.yml"
    assert context.repository_config is None
    assert context.config["project"]["name"] == "legacy"
