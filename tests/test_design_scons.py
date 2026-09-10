"""Selective design rendering with SCons

Checks:
Generated design images behave as independent SCons targets: a cold build renders both
sample images, an unchanged second build renders none, and changing the source for one
component rerenders only that component's image.

Testing approach:
This is an integration test rather than a simulated unit test. It creates two tiny real
OpenSCAD components and runs the actual SCons/OpenSCAD design build three times, then
reads the generated build report and checks the output files. The test is skipped when
the required SCAD toolchain programs are not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scad_project.config import ProjectContext
from scad_project.design_scons import build_design


pytestmark = pytest.mark.skipif(
    any(shutil.which(name) is None for name in ("scons", "openscad", "xvfb-run")),
    reason="selective design integration test requires the SCAD toolchain",
)


def _component(root: Path, name: str, size: int) -> None:
    component = root / "dsg" / "components" / name
    design = component / "design"
    design.mkdir(parents=True)

    (component / f"{name}.scad").write_text(
        f'module {name}_design(view="final") {{ cube({size}); }}\n',
        encoding="utf-8",
    )
    (design / "design.md").write_text(
        f"""# {name}

<!-- scad-render-defaults
module: {name}_design
-->

<!-- scad-render
view: final
-->
""",
        encoding="utf-8",
    )


def _context(tmp_path: Path) -> ProjectContext:
    _component(tmp_path, "alpha", 1)
    _component(tmp_path, "beta", 2)

    config = {
        "project": {"name": "design-selective-test"},
        "paths": {
            "design_root": "dsg",
            "build_root": "bld",
        },
        "build_engine": {"engine": "scons"},
        "openscad": {
            "common_flags": [],
            "render_flags": ["--render"],
            "image_size": [120, 90],
            "design_image_size": [120, 90],
        },
        "externals": [],
    }
    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def _report(tmp_path: Path) -> dict:
    path = (
        tmp_path
        / ".cache"
        / "scad-project"
        / "state"
        / "last-design-build.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_design_images_are_individual_scons_targets(tmp_path: Path):
    context = _context(tmp_path)

    # Cold build: both independent image targets must execute and populate cache.
    build_design(context)
    first = _report(tmp_path)
    assert first["target_count"] == 2
    assert first["executed_count"] == 2

    # Identical second build: SCons should execute no render target at all.
    build_design(context)
    second = _report(tmp_path)
    assert second["target_count"] == 2
    assert second["executed_count"] == 0

    alpha = tmp_path / "dsg" / "components" / "alpha" / "alpha.scad"
    alpha.write_text(
        'module alpha_design(view="final") { cube(3); }\n',
        encoding="utf-8",
    )

    # Change only alpha: alpha rerenders while beta remains a reusable target.
    build_design(context)
    third = _report(tmp_path)
    assert third["target_count"] == 2
    assert third["executed_count"] == 1
    assert third["executed"][0].endswith(
        "components/alpha/design/img/01-final.png"
    )

    assert (
        tmp_path
        / "bld"
        / "design"
        / "project"
        / "components"
        / "alpha"
        / "design"
        / "img"
        / "01-final.png"
    ).is_file()
    assert (
        tmp_path
        / "bld"
        / "design"
        / "project"
        / "components"
        / "beta"
        / "design"
        / "img"
        / "01-final.png"
    ).is_file()
