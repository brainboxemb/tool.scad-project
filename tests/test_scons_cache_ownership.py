"""Production SCons cache ownership wiring

Checks:
Normal builds and verification builds bind their manifests to different production
CacheDir roots. Combined with the real-SCons cross-cache conformance scenario, this
proves that the production wiring preserves the intended cache ownership boundary.

Testing approach:
The test constructs minimal normal-build and verification targets through the real
manifest writers, then asserts each manifest uses its owning module's declared cache
root and that those roots are distinct. No renderer or SCons process is needed here;
the separate real-SCons conformance test proves the behavioral consequence of using
separate CacheDirs.
"""

from __future__ import annotations

import json
from pathlib import Path

from scad_project import build_engine, verification
from scad_project.config import ProjectContext


def _context(tmp_path: Path) -> ProjectContext:
    normal = tmp_path / "dsg" / "render" / "part.scad"
    verify = tmp_path / "vrf" / "openscad" / "fit.scad"
    normal.parent.mkdir(parents=True)
    verify.parent.mkdir(parents=True)
    normal.write_text("cube(1);\n", encoding="utf-8")
    verify.write_text("sphere(1);\n", encoding="utf-8")

    return ProjectContext(
        root=tmp_path,
        config_file=tmp_path / "project.yml",
        config={
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "openscad": {"image_size": [100, 80]},
            "externals": [],
            "build_engine": {"engine": "scons"},
        },
    )


def test_normal_and_verification_manifests_use_distinct_production_cache_roots(
    tmp_path: Path,
    monkeypatch,
):
    context = _context(tmp_path)
    monkeypatch.setattr(build_engine, "_backend_signature", lambda: "backend-test")

    normal_manifest = build_engine._write_manifest(
        context,
        [
            {
                "source": tmp_path / "dsg" / "render" / "part.scad",
                "output": tmp_path / "bld" / "stl" / "part.stl",
                "image_size": (100, 80),
                "definitions": [],
            }
        ],
        common=[],
        render_flags=[],
        watermark_text=None,
    )
    verification_manifest = verification._write_verification_manifest(
        context,
        [
            {
                "source": tmp_path / "vrf" / "openscad" / "fit.scad",
                "output": tmp_path / "vrf" / "out" / "stl" / "fit.stl",
                "image_size": (100, 80),
                "definitions": [],
            }
        ],
    )

    normal = json.loads(normal_manifest.read_text(encoding="utf-8"))
    verify = json.loads(verification_manifest.read_text(encoding="utf-8"))

    assert build_engine.SCONS_CACHE_ROOT != verification.VERIFICATION_SCONS_CACHE_ROOT
    assert normal["cache_root"] == str(tmp_path / build_engine.SCONS_CACHE_ROOT)
    assert verify["cache_root"] == str(
        tmp_path / verification.VERIFICATION_SCONS_CACHE_ROOT
    )
    assert normal["cache_root"] != verify["cache_root"]
