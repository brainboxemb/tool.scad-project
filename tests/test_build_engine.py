"""Build engine selection

Checks:
The direct build engine remains the default, `scons` can be selected explicitly, invalid
engine names are rejected, and selecting SCons without SCons installed gives a clear
error. The SCons handoff must contain the same target details as the normal build path,
and its report must distinguish outputs built now from outputs reused from cache.

Testing approach:
The tests build a minimal in-memory project configuration and inspect the generated
SCons manifest/report JSON. Where backend selection or SCons availability must be
controlled, pytest's `monkeypatch` fixture temporarily replaces the relevant function
with a predictable result. No CAD renderer is required for these unit-level checks.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def test_manifest_reuses_existing_target_model(tmp_path, monkeypatch):
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

    assert payload["cache_root"] == str(
        tmp_path / ".cache" / "scad-project" / "scons"
    )
    assert payload["targets"] == [
        {
            "source": "dsg/render/part.scad",
            "output": "bld/png/part.png",
            "image_size": [800, 600],
            "definitions": [],
            "common_flags": ["--enable=object-function"],
            "render_flags": ["--render"],
            "watermark_text": None,
            "backend_signature": "backend-test",
        }
    ]


def test_report_distinguishes_executed_and_not_executed_targets(tmp_path):
    context = _context(tmp_path, engine="scons")
    state = tmp_path / ".cache" / "scad-project" / "state"
    state.mkdir(parents=True)
    execution_log = state / "executed-targets.txt"
    execution_log.write_text("bld/png/a.png\n", encoding="utf-8")
    manifest = state / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "execution_log": str(execution_log),
                "targets": [
                    {"output": "bld/png/a.png"},
                    {"output": "bld/png/b.png"},
                ],
            }
        ),
        encoding="utf-8",
    )

    build_engine._write_report(context, manifest)

    report = json.loads((state / "last-build.json").read_text(encoding="utf-8"))
    assert report["executed"] == ["bld/png/a.png"]
    assert report["not_executed"] == ["bld/png/b.png"]
    assert report["executed_count"] == 1
    assert report["not_executed_count"] == 1
