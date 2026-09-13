"""Deterministic SCons target-decision conformance

Checks:
The real selective SCons driver produces the exact Step-1 outcomes expected for
cold/current builds, private/shared dependency invalidation, static import/surface
assets, target-spec and backend-signature changes, local missing-output repair,
fresh-runner and partial CacheDir restores, target add/remove changes, and isolated
build/verification caches. The suite also records the pinned SCons behavior that a
readable but externally modified cache payload is still restored by build-signature
key; CACHE_RESTORED is therefore a decision outcome, not artifact-integrity proof.

Testing approach:
Each test writes a tiny OpenSCAD dependency graph and invokes the repository's real
`scons_driver.py`. A temporary fake `openscad` executable creates non-empty STL
outputs so the test exercises the production dependency scanner, target-spec Value
signature, SCons state/cache behavior and structured decision reporter without doing
CAD rendering. Fresh-runner cases remove outputs and SCons state and restore only a
copied CacheDir snapshot. Assertions use machine-readable target outcomes and action
flags instead of parsing SCons console wording.
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


def _target_spec(
    root: Path,
    name: str,
    *,
    backend_signature: str = "backend-v1",
    definitions: tuple[str, ...] = (),
) -> dict:
    source = root / "src" / f"{name}.scad"
    sources = [source, *scan_openscad_dependencies(source)]
    return {
        "source": _relative(root, source),
        "output": f"bld/{name}.stl",
        "image_size": [64, 64],
        "definitions": list(definitions),
        "common_flags": [],
        "render_flags": [],
        "watermark_text": None,
        "backend_signature": backend_signature,
        "sources": [_relative(root, path) for path in sources],
    }


def _prepare_project(root: Path) -> None:
    _write(
        root / "src" / "a.scad",
        """include <shared.scad>
use <private-a.scad>
import("mesh-a.stl");
surface(file="height-a.dat");
cube(1);
""",
    )
    _write(
        root / "src" / "b.scad",
        "include <shared.scad>\nuse <private-b.scad>\nsphere(1);\n",
    )
    _write(root / "src" / "shared.scad", "SHARED = 1;\n")
    _write(root / "src" / "private-a.scad", "A = 1;\n")
    _write(root / "src" / "private-b.scad", "B = 1;\n")
    _write(root / "src" / "mesh-a.stl", "solid a\nendsolid a\n")
    _write(root / "src" / "height-a.dat", "0 0\n0 0\n")


def _new_project(tmp_path: Path, name: str = "project") -> tuple[Path, Path]:
    project = tmp_path / name
    fake_bin = tmp_path / f"{name}-bin"
    project.mkdir()
    fake_bin.mkdir()
    _prepare_project(project)
    _create_fake_openscad(fake_bin)
    return project, fake_bin


def _run(
    root: Path,
    cache: Path,
    fake_bin: Path,
    *,
    names: tuple[str, ...] = ("a", "b"),
    backend_signature: str = "backend-v1",
    definitions: dict[str, tuple[str, ...]] | None = None,
    state_name: str = "build",
) -> dict:
    state = root / ".state"
    state.mkdir(parents=True, exist_ok=True)
    execution_log = state / f"{state_name}-executed-targets.txt"
    execution_log.unlink(missing_ok=True)
    definitions = definitions or {}

    targets = [
        _target_spec(
            root,
            name,
            backend_signature=backend_signature,
            definitions=definitions.get(name, ()),
        )
        for name in names
    ]
    build_decisions.capture_output_state(root, targets)

    manifest = state / f"{state_name}-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": build_decisions.MANIFEST_SCHEMA_VERSION,
                "project_root": str(root.resolve()),
                "cache_root": str(cache.resolve()),
                "sconsign": str((state / f".{state_name}.sconsign.dblite").resolve()),
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
        report_path=state / f"last-{state_name}-conformance.json",
        report_kind=f"conformance-{state_name}",
        backend_signature=backend_signature,
    )


def _outcomes(report: dict) -> dict[str, str]:
    return {target["output"]: target["outcome"] for target in report["targets"]}


def _action_flags(report: dict) -> dict[str, bool]:
    return {
        target["output"]: target["action_executed"]
        for target in report["targets"]
    }


def _fresh_runner(root: Path) -> None:
    shutil.rmtree(root / "bld", ignore_errors=True)
    shutil.rmtree(root / ".state", ignore_errors=True)


def _copy_cache(source: Path, destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(source, destination)


def _cache_entry_with_payload(cache: Path, payload: bytes) -> Path:
    matches = [
        path
        for path in cache.rglob("*")
        if path.is_file() and path.read_bytes() == payload
    ]
    assert len(matches) == 1, [str(path) for path in matches]
    return matches[0]


def _require_scons() -> None:
    if shutil.which("scons") is None:
        pytest.skip("SCons conformance dependency is not installed")


def test_cold_then_identical_run_is_built_then_current(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"

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
    assert _action_flags(unchanged) == {
        "bld/a.stl": False,
        "bld/b.stl": False,
    }


def test_private_and_shared_dependency_changes_are_selective(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin)

    _write(project / "src" / "private-a.scad", "A = 200;\n")
    private_change = _run(project, cache, fake_bin)
    assert _outcomes(private_change) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "CURRENT",
    }

    _write(project / "src" / "shared.scad", "SHARED = 200;\n")
    shared_change = _run(project, cache, fake_bin)
    assert _outcomes(shared_change) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "BUILT",
    }


@pytest.mark.parametrize(
    ("asset", "replacement"),
    [
        ("mesh-a.stl", "solid changed-a\nendsolid changed-a\n"),
        ("height-a.dat", "0 0 0\n0 0 0\n0 0 0\n"),
    ],
)
def test_static_import_and_surface_asset_changes_are_selective(
    tmp_path: Path,
    asset: str,
    replacement: str,
):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin)

    _write(project / "src" / asset, replacement)
    changed = _run(project, cache, fake_bin)
    assert _outcomes(changed) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "CURRENT",
    }


def test_target_spec_and_backend_signature_changes_invalidate_expected_targets(
    tmp_path: Path,
):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin)

    definitions = {"a": ("PROFILE=2",)}
    spec_change = _run(
        project,
        cache,
        fake_bin,
        definitions=definitions,
    )
    assert _outcomes(spec_change) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "CURRENT",
    }

    backend_change = _run(
        project,
        cache,
        fake_bin,
        definitions=definitions,
        backend_signature="backend-v2",
    )
    assert _outcomes(backend_change) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "BUILT",
    }


def test_missing_output_with_local_state_is_restored_from_cache(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin)

    (project / "bld" / "a.stl").unlink()
    repaired = _run(project, cache, fake_bin)
    assert _outcomes(repaired) == {
        "bld/a.stl": "CACHE_RESTORED",
        "bld/b.stl": "CURRENT",
    }
    assert _action_flags(repaired) == {
        "bld/a.stl": False,
        "bld/b.stl": False,
    }


def test_fresh_runner_restores_complete_copied_cache_without_actions(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    original_cache = tmp_path / "original-cache"
    restored_cache = tmp_path / "restored-cache"
    _run(project, original_cache, fake_bin)
    _copy_cache(original_cache, restored_cache)

    _fresh_runner(project)
    restored = _run(project, restored_cache, fake_bin)
    assert _outcomes(restored) == {
        "bld/a.stl": "CACHE_RESTORED",
        "bld/b.stl": "CACHE_RESTORED",
    }
    assert _action_flags(restored) == {
        "bld/a.stl": False,
        "bld/b.stl": False,
    }


def test_partial_cache_restores_available_target_and_builds_missing_target(
    tmp_path: Path,
):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "partial-cache"
    _run(project, cache, fake_bin, names=("a",))

    _fresh_runner(project)
    partial = _run(project, cache, fake_bin, names=("a", "b"))
    assert _outcomes(partial) == {
        "bld/a.stl": "CACHE_RESTORED",
        "bld/b.stl": "BUILT",
    }
    assert _action_flags(partial) == {
        "bld/a.stl": False,
        "bld/b.stl": True,
    }


def test_readable_mutated_cache_payload_is_still_restored_by_scons(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin, names=("a",))

    built_payload = (project / "bld" / "a.stl").read_bytes()
    cache_entry = _cache_entry_with_payload(cache, built_payload)
    corrupted_payload = b"externally-mutated-cache-payload\n"
    cache_entry.write_bytes(corrupted_payload)

    _fresh_runner(project)
    restored = _run(project, cache, fake_bin, names=("a",))
    assert _outcomes(restored) == {"bld/a.stl": "CACHE_RESTORED"}
    assert _action_flags(restored) == {"bld/a.stl": False}
    assert (project / "bld" / "a.stl").read_bytes() == corrupted_payload


def test_adding_and_removing_targets_only_changes_active_required_work(tmp_path: Path):
    _require_scons()
    project, fake_bin = _new_project(tmp_path)
    cache = tmp_path / "cache"
    _run(project, cache, fake_bin)

    _write(
        project / "src" / "c.scad",
        "include <shared.scad>\nuse <private-c.scad>\ncylinder(1);\n",
    )
    _write(project / "src" / "private-c.scad", "C = 1;\n")
    added = _run(project, cache, fake_bin, names=("a", "b", "c"))
    assert _outcomes(added) == {
        "bld/a.stl": "CURRENT",
        "bld/b.stl": "CURRENT",
        "bld/c.stl": "BUILT",
    }

    removed = _run(project, cache, fake_bin, names=("a", "c"))
    assert _outcomes(removed) == {
        "bld/a.stl": "CURRENT",
        "bld/c.stl": "CURRENT",
    }
    assert removed["target_count"] == 2
    assert (project / "bld" / "b.stl").is_file()


def test_build_and_verification_cache_scopes_do_not_cross_restore(tmp_path: Path):
    _require_scons()

    build_first, build_bin = _new_project(tmp_path, "build-first")
    build_cache = tmp_path / "build-cache"
    empty_verify_cache = tmp_path / "empty-verify-cache"
    _run(build_first, build_cache, build_bin, state_name="build")
    _fresh_runner(build_first)
    verify_without_verify_cache = _run(
        build_first,
        empty_verify_cache,
        build_bin,
        state_name="verify",
    )
    assert _outcomes(verify_without_verify_cache) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "BUILT",
    }

    verify_first, verify_bin = _new_project(tmp_path, "verify-first")
    verify_cache = tmp_path / "verify-cache"
    empty_build_cache = tmp_path / "empty-build-cache"
    _run(verify_first, verify_cache, verify_bin, state_name="verify")
    _fresh_runner(verify_first)
    build_without_build_cache = _run(
        verify_first,
        empty_build_cache,
        verify_bin,
        state_name="build",
    )
    assert _outcomes(build_without_build_cache) == {
        "bld/a.stl": "BUILT",
        "bld/b.stl": "BUILT",
    }
