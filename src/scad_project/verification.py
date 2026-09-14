"""Run dependency-aware verification targets and project-specific checks."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from . import build as direct_build
from . import build_decisions
from . import build_engine
from .config import ProjectContext
from .execution_evidence import append_evidence_navigation, write_execution_evidence
from .process import run_checked


VERIFICATION_SCONS_CACHE_ROOT = ".cache/scad-project/verification-scons"
VERIFICATION_SCONS_STATE_ROOT = ".cache/scad-project/verification-state"


def verification_commands(context: ProjectContext) -> list[list[str]]:
    """Return validated argv-style verification commands."""

    verification = context.config.get("verification", {}) or {}
    raw = verification.get("commands", []) or []
    commands: list[list[str]] = []

    for index, command in enumerate(raw):
        if not isinstance(command, list) or not command:
            raise RuntimeError(
                f"verification.commands[{index}] must be a non-empty argv list"
            )
        if not all(isinstance(value, (str, int, float)) for value in command):
            raise RuntimeError(
                f"verification.commands[{index}] values must be scalar strings/numbers"
            )
        commands.append([str(value) for value in command])

    return commands


def _verification_directory_targets(
    context: ProjectContext,
    *,
    kind: str,
    source_root_value: str,
    output_root_value: str,
    default_image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    source_root = context.path(source_root_value)
    config_name = "render.yml" if kind == "render" else "export.yml"
    directory_config = direct_build._load_directory_config(source_root / config_name)
    profiles = direct_build._profile_map(directory_config)
    defaults = directory_config.get("defaults", {}) or {}

    if not source_root.is_dir():
        print(f"WARNING: verification {kind} directory does not exist; skipping: {source_root}")
        return []

    entrypoints = sorted(
        path for path in source_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".scad"
    )
    entrypoint_names = {path.name for path in entrypoints}

    unknown_profile_files = sorted(set(profiles) - entrypoint_names)
    if unknown_profile_files:
        names = ", ".join(unknown_profile_files)
        raise RuntimeError(
            f"{source_root / config_name}: profile file(s) not found in "
            f"{source_root}: {names}"
        )

    output_root = context.path(output_root_value)
    output_dir = output_root / ("png" if kind == "render" else "stl")
    extension = ".png" if kind == "render" else ".stl"
    default_size = direct_build._validate_image_size(
        defaults.get("image_size", default_image_size),
        f"{source_root / config_name}: effective default image_size",
    )

    targets: list[dict[str, Any]] = []
    for source in entrypoints:
        profile = profiles.get(source.name, {})
        sizes = profile.get("sizes")
        image_size = direct_build._validate_image_size(
            profile.get("image_size", default_size),
            f"{source_root / config_name}: effective image_size for {source.name}",
        )
        output_pattern = profile.get("output_pattern")
        if output_pattern is not None and (
            not isinstance(output_pattern, str) or not output_pattern.strip()
        ):
            raise RuntimeError(
                f"{source_root / config_name}: profile output_pattern for "
                f"{source.name} must be a non-empty string"
            )

        variants = sizes if sizes is not None else [None]
        for size_name in variants:
            slug = direct_build._slug(source.stem)
            if output_pattern:
                try:
                    output_name = output_pattern.format(
                        stem=slug,
                        size=size_name or "",
                        ext=extension.lstrip("."),
                    )
                except (KeyError, ValueError) as exc:
                    raise RuntimeError(
                        f"{source_root / config_name}: invalid output_pattern "
                        f"for {source.name}: {output_pattern}"
                    ) from exc
                if Path(output_name).name != output_name:
                    raise RuntimeError(
                        f"{source_root / config_name}: output_pattern for "
                        f"{source.name} must produce a filename, not a path"
                    )
                if Path(output_name).suffix.lower() != extension:
                    raise RuntimeError(
                        f"{source_root / config_name}: output_pattern for "
                        f"{source.name} must end in {extension}"
                    )
            else:
                suffix = f"-{size_name}" if size_name is not None else ""
                output_name = f"{slug}{suffix}{extension}"

            definitions = (
                [f'size="{size_name}"'] if size_name is not None else []
            )
            targets.append(
                {
                    "source": source,
                    "output": output_dir / output_name,
                    "image_size": image_size,
                    "definitions": definitions,
                }
            )

    return targets


def verification_targets(context: ProjectContext) -> list[dict[str, Any]]:
    """Resolve verification-only OpenSCAD targets without using normal build output."""

    verification = context.config.get("verification", {}) or {}
    render_root = verification.get("render_root")
    export_root = verification.get("export_root")
    if not render_root and not export_root:
        return []

    output_root = str(verification.get("output_root", "vrf/out"))
    osc = context.config.get("openscad", {}) or {}
    default_image_size = direct_build._validate_image_size(
        verification.get("image_size", osc.get("image_size", [1600, 1000])),
        "verification.image_size",
    )

    targets: list[dict[str, Any]] = []
    if render_root:
        targets.extend(
            _verification_directory_targets(
                context,
                kind="render",
                source_root_value=str(render_root),
                output_root_value=output_root,
                default_image_size=default_image_size,
            )
        )
    if export_root:
        targets.extend(
            _verification_directory_targets(
                context,
                kind="export",
                source_root_value=str(export_root),
                output_root_value=output_root,
                default_image_size=default_image_size,
            )
        )
    return targets


def _write_verification_manifest(
    context: ProjectContext,
    targets: list[dict[str, Any]],
) -> Path:
    state_root = context.path(VERIFICATION_SCONS_STATE_ROOT)
    state_root.mkdir(parents=True, exist_ok=True)
    manifest = state_root / "verification-manifest.json"

    osc = context.config.get("openscad", {}) or {}
    common = [str(value) for value in osc.get("common_flags", [])]
    render_flags = [str(value) for value in osc.get("render_flags", ["--render"])]
    watermark_text = direct_build._watermark_text(context)
    backend_signature = build_engine._backend_signature()
    search_paths = build_engine._search_paths(context)
    target_specs = [
        build_engine._target_spec(
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
        spec["sources"] = build_engine._target_sources(
            context,
            spec,
            search_paths=search_paths,
        )
    build_decisions.capture_output_state(context.root, target_specs)

    payload = {
        "schema_version": build_decisions.MANIFEST_SCHEMA_VERSION,
        "project_root": str(context.root.resolve()),
        "cache_root": str(context.path(VERIFICATION_SCONS_CACHE_ROOT)),
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


def _write_verification_report(
    context: ProjectContext,
    manifest: Path,
) -> dict[str, Any]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    backend_signature = (
        payload["targets"][0].get("backend_signature")
        if payload.get("targets")
        else None
    )
    report = build_decisions.write_decision_report(
        project_root=context.root,
        manifest=manifest,
        report_path=context.path(VERIFICATION_SCONS_STATE_ROOT)
        / "last-verification-build.json",
        report_kind="verification",
        backend_signature=backend_signature,
    )
    build_decisions.print_decision_summary("Verification SCons summary", report)
    return report


def build_verification_targets(context: ProjectContext) -> None:
    """Build verification-only targets with a cache separate from normal build output."""

    targets = verification_targets(context)
    if not targets:
        return

    if build_engine._engine_name(context) != "scons":
        raise RuntimeError(
            "verification render/export targets require build_engine.engine: scons"
        )
    if shutil.which("scons") is None:
        raise RuntimeError(
            "Verification targets require SCons but 'scons' is not installed"
        )

    manifest = _write_verification_manifest(context, targets)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    Path(payload["execution_log"]).unlink(missing_ok=True)

    driver = Path(build_engine.__file__).with_name("scons_driver.py").resolve()
    print(
        f"Verification SCons engine: {len(targets)} target(s), "
        f"cache={context.path(VERIFICATION_SCONS_CACHE_ROOT)}"
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
        _write_verification_report(context, manifest)


def run_functional_verification(context: ProjectContext) -> None:
    """Build declared verification targets, then run project checks in repository order."""

    targets = verification_targets(context)
    commands = verification_commands(context)
    if not targets and not commands:
        raise RuntimeError("No verification targets or commands are configured")

    # Keep this call observable for tests and future instrumentation while avoiding
    # duplicate target discovery inside build_verification_targets.
    build_verification_targets(context)

    for command in commands:
        run_checked(command, cwd=context.root)

    verification = context.config.get("verification", {}) or {}
    output_root = context.path(str(verification.get("output_root", "vrf/out")))
    report = context.path(VERIFICATION_SCONS_STATE_ROOT) / "last-verification-build.json"
    write_execution_evidence(
        context,
        capability="scad.verify",
        action="verify",
        execution_id="scad-verify",
        output_root=output_root,
        domain_report=report,
    )
    append_evidence_navigation(output_root / "README.md", output_root)
