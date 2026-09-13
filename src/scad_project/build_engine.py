"""Select the configured build backend while preserving one target model."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from . import build as direct_build
from . import build_decisions
from .config import ProjectContext
from .openscad_deps import scan_openscad_dependencies
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


def _target_sources(
    context: ProjectContext,
    spec: dict[str, Any],
    *,
    search_paths: list[str],
) -> list[str]:
    """Resolve the OpenSCAD source/dependency set recorded in telemetry."""

    source = Path(str(spec["source"]))
    if not source.is_absolute():
        source = context.root / source
    source = source.resolve()
    dependencies = scan_openscad_dependencies(
        source,
        search_paths=[Path(value).resolve() for value in search_paths],
    )
    ordered = [source, *dependencies]
    result: list[str] = []
    seen: set[str] = set()
    for path in ordered:
        value = _relative_or_absolute(context.root, path)
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


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
    search_paths = _search_paths(context)
    target_specs = [
        _target_spec(
            context,
            target,
            common=common,
            render_flags=render_flags,
            watermark_text=watermark_text,
            backend_signature=backend_signature,
        )
        for target in targets
    ]
    for spec in target_specs:
        spec["sources"] = _target_sources(
            context,
            spec,
            search_paths=search_paths,
        )
    build_decisions.capture_output_state(context.root, target_specs)

    payload = {
        "schema_version": build_decisions.MANIFEST_SCHEMA_VERSION,
        "project_root": str(context.root.resolve()),
        "cache_root": str(context.path(SCONS_CACHE_ROOT)),
        "sconsign": str(state_root / ".sconsign.dblite"),
        "execution_log": str(state_root / "executed-targets.txt"),
        "search_paths": search_paths,
        "targets": target_specs,
    }
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_report(context: ProjectContext, manifest: Path) -> dict[str, Any]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    backend_signature = (
        payload["targets"][0].get("backend_signature")
        if payload.get("targets")
        else None
    )
    report = build_decisions.write_decision_report(
        project_root=context.root,
        manifest=manifest,
        report_path=context.path(SCONS_STATE_ROOT) / "last-build.json",
        report_kind="build",
        backend_signature=backend_signature,
    )
    build_decisions.print_decision_summary("SCons summary", report)
    return report


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
    try:
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
    finally:
        _write_report(context, manifest)


def build_project(context: ProjectContext) -> None:
    """Build through the selected backend; direct remains the default."""

    engine = _engine_name(context)
    if engine == "direct":
        direct_build.build_project(context)
        return

    _build_with_scons(context)
