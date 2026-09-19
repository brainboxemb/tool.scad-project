"""Build engine selection and structured normal-build reporting

Checks:
The direct build engine remains the default, `scons` can be selected explicitly, invalid
engine names are rejected, and selecting SCons without SCons installed gives a clear
error. The SCons handoff must contain the same target details as the normal build path,
plus pre-build/source telemetry, and its report must use the shared explicit outcome
schema rather than the old executed/not-executed split.

Testing approach:
The tests build a minimal in-memory project configuration and inspect the generated
SCons manifest/report JSON. Where backend selection or SCons availability must be
controlled, pytest's `monkeypatch` fixture temporarily replaces the relevant function
with a predictable result. No CAD renderer is required for these unit-level checks.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

import scad_project.build_engine as build_engine
from scad_project.config import ProjectContext


def _context(tmp_path: Path, *, engine: str | None = None) -> ProjectContext:
    source = tmp_path / "dsg" / "render" / "part.scad"
    source.parent.mkdir(parents=True)
    source.write_text("cube(1);\n", encoding="utf-8")

    config = {
        "project": {"name": "demo"},
        "paths": {
            "design_root": "dsg",
            "build_root": "bld",
        },
        "openscad": {
            "common_flags": ["--enable=object-function"],
            "render_flags": ["--render"],
            "image_size": [800, 600],
        },
        "externals": [],
        "builds": [
            {
                "name": "part-png",
                "source": "dsg/render/part.scad",
                "output": "bld/png/part.png",
            }
        ],
    }
    if engine is not None:
        config["build_engine"] = {"engine": engine}

    return ProjectContext(tmp_path, tmp_path / "project.yml", config)


def test_direct_engine_remains_default(tmp_path, monkeypatch):
    called = []

    monkeypatch.setattr(
        build_engine.direct_build,
        "build_project",
        lambda context: called.append(context.root),
    )

    build_engine.build_project(_context(tmp_path))

    assert called == [tmp_path]


def test_unknown_engine_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="direct.*scons"):
        build_engine.build_project(_context(tmp_path, engine="magic"))


def test_scons_engine_requires_scons(tmp_path, monkeypatch):
    monkeypatch.setattr(build_engine.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="scons.*not installed"):
        build_engine.build_project(_context(tmp_path, engine="scons"))


def test_manifest_reuses_existing_target_model_and_adds_telemetry(tmp_path, monkeypatch):
    context = _context(tmp_path, engine="scons")
    monkeypatch.setattr(build_engine, "_backend_signature", lambda: "backend-test")

    targets = build_engine.direct_build._build_targets(
        context,
        (800, 600),
    )
    manifest = build_engine._write_manifest(
        context,
        targets,
        common=["--enable=object-function"],
        render_flags=["--render"],
        watermark_text=None,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["cache_root"] == str(
        tmp_path / ".cache" / "scad-project" / "scons"
    )
    assert payload["targets"] == [
        {
            "source": "dsg/render/part.scad",
            "output": "bld/png/part.png",
            "format": "png",
            "image_size": [800, 600],
            "definitions": [],
            "common_flags": ["--enable=object-function"],
            "render_flags": ["--render"],
            "watermark_text": None,
            "backend_signature": "backend-test",
            "sources": ["dsg/render/part.scad"],
            "existed_before": False,
        }
    ]


def test_report_uses_structured_outcomes(tmp_path):
    context = _context(tmp_path, engine="scons")
    state = tmp_path / ".cache" / "scad-project" / "state"
    state.mkdir(parents=True)
    execution_log = state / "executed-targets.txt"
    execution_log.write_text("bld/png/a.png\n", encoding="utf-8")

    for relative in ("bld/png/a.png", "bld/png/b.png"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("output", encoding="utf-8")

    manifest = state / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_log": str(execution_log),
                "targets": [
                    {
                        "output": "bld/png/a.png",
                        "source": "dsg/a.scad",
                        "sources": ["dsg/a.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": False,
                    },
                    {
                        "output": "bld/png/b.png",
                        "source": "dsg/b.scad",
                        "sources": ["dsg/b.scad"],
                        "backend_signature": "backend-test",
                        "existed_before": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_engine._write_report(context, manifest)

    assert report["schema"] == "scad-project.build-decisions"
    assert report["kind"] == "build"
    assert report["outcome_counts"] == {
        "BUILT": 1,
        "CACHE_RESTORED": 0,
        "CURRENT": 1,
        "ERROR": 0,
    }
    assert [target["outcome"] for target in report["targets"]] == [
        "BUILT",
        "CURRENT",
    ]


def test_scons_engine_builds_explicit_svg_output(tmp_path):
    if shutil.which("scons") is None or shutil.which("openscad") is None:
        pytest.skip("SCons/OpenSCAD runtime is not installed")

    source = tmp_path / "dsg" / "drawing" / "receiver.scad"
    source.parent.mkdir(parents=True)
    source.write_text("square([10, 6]);\n", encoding="utf-8")

    context = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "openscad": {"image_size": [800, 600]},
            "externals": [],
            "build_engine": {"engine": "scons"},
            "builds": [
                {
                    "name": "receiver-drawing",
                    "source": "dsg/drawing/receiver.scad",
                    "output": "bld/svg/receiver.svg",
                }
            ],
        },
    )

    build_engine.build_project(context)

    output = tmp_path / "bld" / "svg" / "receiver.svg"
    assert output.is_file()
    assert "<svg" in output.read_text(encoding="utf-8").lower()


def test_scons_render_format_change_uses_distinct_cache_target(tmp_path):
    if shutil.which("scons") is None or shutil.which("openscad") is None:
        pytest.skip("SCons/OpenSCAD runtime is not installed")

    render_dir = tmp_path / "dsg" / "render"
    render_dir.mkdir(parents=True)
    source = render_dir / "drawing.scad"
    source.write_text("square([10, 6]);\n", encoding="utf-8")
    config_file = render_dir / "render.yml"

    context = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {
                "design_root": "dsg",
                "build_root": "bld",
                "render_root": "dsg/render",
            },
            "openscad": {"image_size": [160, 100]},
            "externals": [],
            "build_engine": {"engine": "scons"},
        },
    )

    config_file.write_text("defaults:\n  format: png\n", encoding="utf-8")
    build_engine.build_project(context)
    assert (tmp_path / "bld" / "png" / "drawing.png").is_file()

    config_file.write_text("defaults:\n  format: svg\n", encoding="utf-8")
    build_engine.build_project(context)
    svg = tmp_path / "bld" / "svg" / "drawing.svg"
    assert svg.is_file()

    report_path = (
        tmp_path
        / ".cache"
        / "scad-project"
        / "state"
        / "last-build.json"
    )
    changed = json.loads(report_path.read_text(encoding="utf-8"))
    assert changed["targets"][0]["output"] == "bld/svg/drawing.svg"
    assert changed["targets"][0]["outcome"] == "BUILT"

    svg.unlink()
    build_engine.build_project(context)
    restored = json.loads(report_path.read_text(encoding="utf-8"))
    assert restored["targets"][0]["output"] == "bld/svg/drawing.svg"
    assert restored["targets"][0]["outcome"] == "CACHE_RESTORED"
