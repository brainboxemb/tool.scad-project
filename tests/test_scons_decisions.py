"""Deterministic SCons target-decision conformance

Checks:
The real selective SCons driver classifies a cold build as BUILT and leaves
unchanged targets CURRENT on a second run. The fixture uses the Step-1 structured
decision reporter, so assertions are made against machine-readable outcomes rather
than console wording.

Testing approach:
The test writes a tiny OpenSCAD dependency graph and invokes the repository's real
`scons_driver.py`. A temporary fake `openscad` executable creates non-empty STL
outputs so the test exercises SCons dependency/signature/cache behavior without
performing CAD rendering. Target manifests mirror production target-spec fields,
including the `Value(target-spec)` signature input used by the real driver.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from scad_project import build_decisions
from scad_project.openscad_deps import scan_openscad_dependencies


ROOT = Path(__file__).resolve().parents[1]
SCONS_DRIVER = ROOT / "src" / "scad_project" / "scons_driver.py"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _create_fake_openscad(bin_dir: Path) -> None:
    script = bin_dir / "openscad"
    _write(
        script,
        """#!/usr/bin/env python3
from pathlib import Path
import json
import sys

args = sys.argv[1:]
output = Path(args[args.index("-o") + 1])
source = Path(args[-1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps({"source": source.name, "args": args}, sort_keys=True) + "\\n",
    encoding="utf-8",
)
""",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _target_spec(root: Path, name: str, *, backend_signature: str = "backend-v1") -> dict:
    source = root / "src" / f"{name}.scad"
    sources = [source, *scan_openscad_dependencies(source)]
    return {
        "source": _relative(root, source),
        "output": f"bld/{name}.stl",
        "image_size": [64, 64],
        "definitions": [],
        "common_flags": [],
        "render_flags": [],
        "watermark_text": None,
        "backend_signature": backend_signature,
        "sources": [_relative(root, path) for path in sources],
    }


def _prepare_project(root: Path) -> None:
    _write(
        root / "src" / "a.scad",
        "include <shared.scad>\nuse <private-a.scad>\ncube(1);\n",
    )
    _write(
        root / "src" / "b.scad",
        "include <shared.scad>\nuse <private-b.scad>\nsphere(1);\n",
    )
    _write(root / "src" / "shared.scad", "SHARED = 1;\n")
    _write(root / "src" / "private-a.scad", "A = 1;\n")
    _write(root / "src" / "private-b.scad", "B = 1;\n")


def _run(
    root: Path,
    cache: Path,
    fake_bin: Path,
    *,
    names: tuple[str, ...] = ("a", "b"),
    backend_signature: str = "backend-v1",
) -> dict:
    state = root / ".state"
    state.mkdir(parents=True, exist_ok=True)
    execution_log = state / "executed-targets.txt"
    execution_log.unlink(missing_ok=True)

    targets = [
        _target_spec(root, name, backend_signature=backend_signature)
        for name in names
    ]
    build_decisions.capture_output_state(root, targets)

    manifest = state / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": build_decisions.MANIFEST_SCHEMA_VERSION,
                "project_root": str(root.resolve()),
                "cache_root": str(cache.resolve()),
                "sconsign": str((state / ".sconsign.dblite").resolve()),
                "execution_log": str(execution_log.resolve()),
                "search_paths": [],
                "targets": targets,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = str(fake_bin.resolve()) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            "scons",
            "-Q",
            "-f",
            str(SCONS_DRIVER),
            f"SCAD_PROJECT_MANIFEST={manifest}",
        ],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout

    return build_decisions.write_decision_report(
        project_root=root,
        manifest=manifest,
        report_path=state / "last-conformance.json",
        report_kind="conformance",
        backend_signature=backend_signature,
    )


def _outcomes(report: dict) -> dict[str, str]:
    return {target["output"]: target["outcome"] for target in report["targets"]}


def test_cold_then_identical_run_is_built_then_current(tmp_path: Path):
    if shutil.which("scons") is None:
        pytest.skip("SCons conformance dependency is not installed")

    project = tmp_path / "project"
    fake_bin = tmp_path / "bin"
    cache = tmp_path / "cache"
    project.mkdir()
    fake_bin.mkdir()
    _prepare_project(project)
    _create_fake_openscad(fake_bin)

    cold = _run(project, cache, fake_bin)
    assert _outcomes(cold) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "BUILT",
    }
    assert cold["outcome_counts"]["BUILT"] == 2

    unchanged = _run(project, cache, fake_bin)
    assert _outcomes(unchanged) == {
        "bld/a.stl": "CURRENT",
        "bld/b.stl": "CURRENT",
    }
    assert unchanged["outcome_counts"]["CURRENT"] == 2
