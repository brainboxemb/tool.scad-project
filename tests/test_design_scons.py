"""Selective design rendering with SCons and structured outcomes

Checks:
Generated design images behave as independent SCons targets: a cold build reports both
sample images as BUILT, an unchanged second build restores both into the deliberately
fresh design staging tree as CACHE_RESTORED, and changing one component rebuilds only
that image while the other is restored. Configured watermark post-processing is also
applied to the final design PNG without leaving the raw intermediate behind.

Testing approach:
This is an integration test rather than a simulated unit test. It creates two tiny real
OpenSCAD components and runs the actual SCons/OpenSCAD design build three times, then
reads the generated structured decision report and checks the output files. The test is
skipped when the required SCAD toolchain programs are not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scad_project.config import ProjectContext
from scad_project.design import DesignDocument
from scad_project.design_scons import _write_index, build_design


pytestmark = pytest.mark.skipif(
    any(
        shutil.which(name) is None
        for name in ("scons", "openscad", "xvfb-run", "scad-image-watermark")
    ),
    reason="selective design integration test requires the SCAD toolchain",
)


def _component(
    root: Path,
    name: str,
    size: int,
    *,
    output_format: str = "png",
) -> None:
    component = root / "dsg" / "components" / name
    design = component / "design"
    design.mkdir(parents=True)

    geometry = (
        f"square([{size}, {size}]);"
        if output_format == "svg"
        else f"cube({size});"
    )
    (component / f"{name}.scad").write_text(
        f'module {name}_design(view="final") {{ {geometry} }}\n',
        encoding="utf-8",
    )
    format_line = "\nformat: svg" if output_format == "svg" else ""
    (design / "design.md").write_text(
        f"""# {name}

<!-- scad-render-defaults
module: {name}_design{format_line}
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
        "rendering": {
            "watermark": {
                "text": "© design-test",
            }
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


def _outcomes(report: dict) -> dict[str, str]:
    return {
        Path(target["output"]).name: target["outcome"]
        for target in report["targets"]
    }


def test_design_images_are_individual_scons_targets(tmp_path: Path):
    context = _context(tmp_path)

    # Cold build: both independent image targets execute and populate CacheDir.
    build_design(context)
    first = _report(tmp_path)
    assert first["target_count"] == 2
    assert first["outcome_counts"] == {
        "BUILT": 2,
        "CACHE_RESTORED": 0,
        "CURRENT": 0,
        "ERROR": 0,
    }

    alpha_output = (
        tmp_path
        / "bld"
        / "design"
        / "project"
        / "components"
        / "alpha"
        / "design"
        / "img"
        / "01-final.png"
    )
    assert alpha_output.is_file()
    assert not alpha_output.with_name(".01-final.unwatermarked.png").exists()

    # The design stage is intentionally recreated for every build. An unchanged
    # second run therefore materializes both targets from SCons CacheDir.
    build_design(context)
    second = _report(tmp_path)
    assert second["outcome_counts"] == {
        "BUILT": 0,
        "CACHE_RESTORED": 2,
        "CURRENT": 0,
        "ERROR": 0,
    }

    alpha = tmp_path / "dsg" / "components" / "alpha" / "alpha.scad"
    alpha.write_text(
        'module alpha_design(view="final") { cube(3); }\n',
        encoding="utf-8",
    )

    # Change only alpha: alpha rerenders while beta is restored from CacheDir.
    build_design(context)
    third = _report(tmp_path)
    assert third["outcome_counts"] == {
        "BUILT": 1,
        "CACHE_RESTORED": 1,
        "CURRENT": 0,
        "ERROR": 0,
    }
    outcomes = _outcomes(third)
    assert outcomes["01-final.png"] in {"BUILT", "CACHE_RESTORED"}
    alpha_targets = [
        target for target in third["targets"]
        if "components/alpha/" in target["output"]
    ]
    beta_targets = [
        target for target in third["targets"]
        if "components/beta/" in target["output"]
    ]
    assert [target["outcome"] for target in alpha_targets] == ["BUILT"]
    assert [target["outcome"] for target in beta_targets] == ["CACHE_RESTORED"]

    assert alpha_output.is_file()
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


def test_design_svg_uses_distinct_scons_cache_target(tmp_path: Path):
    _component(tmp_path, "vector", 4, output_format="svg")

    context = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "design-svg-cache-test"},
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
            "rendering": {
                "watermark": {
                    "text": "must-not-apply-to-svg",
                }
            },
            "externals": [],
        },
    )

    build_design(context)
    first = _report(tmp_path)
    assert first["outcome_counts"] == {
        "BUILT": 1,
        "CACHE_RESTORED": 0,
        "CURRENT": 0,
        "ERROR": 0,
    }

    svg = (
        tmp_path
        / "bld"
        / "design"
        / "project"
        / "components"
        / "vector"
        / "design"
        / "img"
        / "01-final.svg"
    )
    assert svg.is_file()
    assert "<svg" in svg.read_text(encoding="utf-8").lower()

    build_design(context)
    second = _report(tmp_path)
    assert second["outcome_counts"] == {
        "BUILT": 0,
        "CACHE_RESTORED": 1,
        "CURRENT": 0,
        "ERROR": 0,
    }
    target = second["targets"][0]
    assert target["output"].endswith("01-final.svg")
    assert target["outcome"] == "CACHE_RESTORED"

    source = tmp_path / "dsg" / "components" / "vector" / "vector.scad"
    source.write_text(
        'module vector_design(view="final") { square([5, 5]); }\n',
        encoding="utf-8",
    )
    build_design(context)
    third = _report(tmp_path)
    assert third["targets"][0]["outcome"] == "BUILT"


def test_scons_index_lists_specifications_before_design_documents(tmp_path: Path):
    stage = tmp_path / "stage"
    stage.mkdir()

    documents = [
        DesignDocument(
            source_file=tmp_path / "specification.md",
            scope="project",
            relative_path=Path("specification/specification.md"),
            document_type="specification",
        ),
        DesignDocument(
            source_file=tmp_path / "design.md",
            scope="project",
            relative_path=Path("components/example/design/design.md"),
            document_type="design",
        ),
    ]

    _write_index(stage, documents)

    text = (stage / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# SCAD engineering documentation\n")
    assert "Generated from source `specification.md` and `design.md` files." in text
    assert text.index("## Specifications") < text.index("## Design documents")
    assert text.index("specification/specification.md") < text.index(
        "components/example/design/design.md"
    )
