"""Select the configured build backend while preserving one target model."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from . import build as direct_build
from .config import ProjectContext
from .process import run_checked


SCONS_CACHE_ROOT = ".cache/scad-project/scons"
SCONS_STATE_ROOT = ".cache/scad-project/state"


def _engine_name(context: ProjectContext) -> str:
    raw = context.config.get("build_engine")
    if raw is None:
        return "direct"
    if not isinstance(raw, dict):
        raise RuntimeError("build_engine must be a mapping")

    value = str(raw.get("engine", "direct")).strip().lower()
    if value not in {"direct", "scons"}:
        raise RuntimeError("build_engine.engine must be 'direct' or 'scons'")
    return value


def _relative_or_absolute(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _search_paths(context: ProjectContext) -> list[str]:
    roots: list[Path] = [context.root.resolve()]

    raw = os.environ.get("OPENSCADPATH", "")
    for value in raw.split(os.pathsep):
        if value.strip():
            roots.append(Path(value).resolve())

    externals = context.config.get("externals")
    if externals is None:
        externals = context.config.get("libraries", [])
    for external in externals or []:
        if not isinstance(external, dict) or not external.get("path"):
            continue
        path = context.path(str(external["path"]))
        roots.extend((path, path.parent))

    result: list[str] = []
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        result.append(str(root))
    return result


def _backend_signature() -> str:
    digest = hashlib.sha256()
    package_root = Path(__file__).resolve().parent
    for name in (
        "build_engine.py",
        "scons_driver.py",
        "openscad_deps.py",
        "process.py",
        "build.py",
    ):
        path = package_root / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())

    digest.update(os.environ.get("SCAD_TOOLCHAIN_IMAGE", "").encode("utf-8"))
    digest.update(os.environ.get("SCAD_TOOLCHAIN_VERSION", "").encode("utf-8"))
    return digest.hexdigest()


def _target_spec(
    context: ProjectContext,
    target: dict[str, Any],
    *,
    common: list[str],
    render_flags: list[str],
    watermark_text: str | None,
    backend_signature: str,
) -> dict[str, Any]:
    return {
        "source": _relative_or_absolute(context.root, target["source"]),
        "output": _relative_or_absolute(context.root, target["output"]),
        "image_size": list(target["image_size"]),
        "definitions": list(target.get("definitions", [])),
        "common_flags": common,
        "render_flags": render_flags,
        "watermark_text": watermark_text,
        "backend_signature": backend_signature,
    }


def _write_manifest(
    context: ProjectContext,
    targets: list[dict[str, Any]],
    *,
    common: list[str],
    render_flags: list[str],
    watermark_text: str | None,
) -> Path:
    state_root = context.path(SCONS_STATE_ROOT)
    state_root.mkdir(parents=True, exist_ok=True)
    manifest = state_root / "build-manifest.json"

    backend_signature = _backend_signature()
    payload = {
        "project_root": str(context.root.resolve()),
        "cache_root": str(context.path(SCONS_CACHE_ROOT)),
        "sconsign": str(state_root / ".sconsign.dblite"),
        "execution_log": str(state_root / "executed-targets.txt"),
        "search_paths": _search_paths(context),
        "targets": [
            _target_spec(
                context,
                target,
                common=common,
                render_flags=render_flags,
                watermark_text=watermark_text,
                backend_signature=backend_signature,
            )
            for target in targets
        ],
    }
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_report(context: ProjectContext, manifest: Path) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    execution_log = Path(payload["execution_log"])
    executed = (
        execution_log.read_text(encoding="utf-8").splitlines()
        if execution_log.is_file()
        else []
    )
    outputs = [spec["output"] for spec in payload["targets"]]
    executed_set = set(executed)
    not_executed = [output for output in outputs if output not in executed_set]

    report = {
        "engine": "scons",
        "target_count": len(outputs),
        "executed_count": len(executed),
        "not_executed_count": len(not_executed),
        "executed": executed,
        "not_executed": not_executed,
    }
    report_path = context.path(SCONS_STATE_ROOT) / "last-build.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "SCons summary: "
        f"targets={len(outputs)} executed={len(executed)} "
        f"not-executed={len(not_executed)}"
    )
    for output in executed:
        print(f"  built: {output}")
    for output in not_executed:
        print(f"  cache/current: {output}")


def _build_with_scons(context: ProjectContext) -> None:
    if shutil.which("scons") is None:
        raise RuntimeError(
            "SCons build engine requested but 'scons' is not installed"
        )

    osc = context.config.get("openscad", {}) or {}
    common = [str(value) for value in osc.get("common_flags", [])]
    render_flags = [
        str(value) for value in osc.get("render_flags", ["--render"])
    ]
    default_image_size = direct_build._validate_image_size(
        osc.get("image_size", [1600, 1000]),
        "openscad.image_size",
    )
    targets = direct_build._build_targets(context, default_image_size)
    if not targets:
        print("No configured build targets.")
        return

    manifest = _write_manifest(
        context,
        targets,
        common=common,
        render_flags=render_flags,
        watermark_text=direct_build._watermark_text(context),
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    Path(payload["execution_log"]).unlink(missing_ok=True)

    driver = Path(__file__).with_name("scons_driver.py").resolve()
    print(
        f"SCons build engine: {len(targets)} target(s), "
        f"cache={context.path(SCONS_CACHE_ROOT)}"
    )
    run_checked(
        [
            "scons",
            "-Q",
            "-f",
            str(driver),
            f"SCAD_PROJECT_MANIFEST={manifest}",
        ],
        cwd=context.root,
    )
    _write_report(context, manifest)


def build_project(context: ProjectContext) -> None:
    """Build through the selected backend; direct remains the default."""

    engine = _engine_name(context)
    if engine == "direct":
        direct_build.build_project(context)
        return

    _build_with_scons(context)
