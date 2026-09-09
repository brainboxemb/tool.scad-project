"""Build OpenSCAD PNG and STL outputs from configured directories or legacy entries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import ProjectContext
from .process import run_checked


def check_libraries(context: ProjectContext) -> list[str]:
    """Compatibility alias for the old ``libraries-check`` command."""

    from .externals import check_externals
    return check_externals(context)


def _watermark_text(context: ProjectContext) -> str | None:
    rendering = context.config.get("rendering", {}) or {}
    watermark = rendering.get("watermark", {}) or {}
    text = watermark.get("text")
    return str(text) if text else None


def _raw_png_path(output: Path) -> Path:
    """Return a temporary PNG path beside the final output."""

    return output.with_name(f".{output.stem}.unwatermarked.png")


def _require_output(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing build output: {path}")


def _load_directory_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping at the root.")

    defaults = data.get("defaults", {}) or {}
    profiles = data.get("profiles", {}) or {}

    if not isinstance(defaults, dict):
        raise RuntimeError(f"{path}: defaults must be a mapping.")
    if not isinstance(profiles, dict):
        raise RuntimeError(f"{path}: profiles must be a mapping.")

    seen_files: set[str] = set()
    for profile_name, profile in profiles.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise RuntimeError(f"{path}: profile names must be non-empty strings.")
        if not isinstance(profile, dict):
            raise RuntimeError(
                f"{path}: profile {profile_name!r} must be a mapping."
            )

        files = profile.get("files", [])
        if not isinstance(files, list) or not files:
            raise RuntimeError(
                f"{path}: profile {profile_name!r}.files must be a non-empty list."
            )

        for filename in files:
            if not isinstance(filename, str) or not filename.strip():
                raise RuntimeError(
                    f"{path}: profile {profile_name!r}.files must contain strings."
                )
            if filename in seen_files:
                raise RuntimeError(
                    f"{path}: {filename!r} is assigned to more than one profile."
                )
            seen_files.add(filename)

        sizes = profile.get("sizes")
        if sizes is not None:
            if not isinstance(sizes, list) or not sizes:
                raise RuntimeError(
                    f"{path}: profile {profile_name!r}.sizes must be a non-empty list."
                )
            if not all(isinstance(size, str) and size.strip() for size in sizes):
                raise RuntimeError(
                    f"{path}: profile {profile_name!r}.sizes must contain strings."
                )

        if "image_size" in profile:
            _validate_image_size(
                profile["image_size"],
                f"{path}: profile {profile_name!r}.image_size",
            )

    if "image_size" in defaults:
        _validate_image_size(defaults["image_size"], f"{path}: defaults.image_size")

    return data


def _validate_image_size(value: Any, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(isinstance(item, int) and item > 0 for item in value)
    ):
        raise RuntimeError(f"{label} must be [WIDTH, HEIGHT] with positive integers.")
    return int(value[0]), int(value[1])


def _profile_map(directory_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for profile in (directory_config.get("profiles", {}) or {}).values():
        for filename in profile.get("files", []):
            result[filename] = profile
    return result


def _slug(stem: str) -> str:
    return stem.replace("_", "-")


def _directory_targets(
    context: ProjectContext,
    *,
    kind: str,
    source_root_value: str,
    default_image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    source_root = context.path(source_root_value)
    config_name = "render.yml" if kind == "render" else "export.yml"
    directory_config = _load_directory_config(source_root / config_name)
    profiles = _profile_map(directory_config)
    defaults = directory_config.get("defaults", {}) or {}

    if not source_root.is_dir():
        print(f"WARNING: {kind} directory does not exist; skipping: {source_root}")
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

    build_root = context.path(context.config["paths"]["build_root"])
    output_dir = build_root / ("png" if kind == "render" else "stl")
    extension = ".png" if kind == "render" else ".stl"

    default_size = _validate_image_size(
        defaults.get("image_size", default_image_size),
        f"{source_root / config_name}: effective default image_size",
    )

    targets: list[dict[str, Any]] = []

    for source in entrypoints:
        profile = profiles.get(source.name, {})
        sizes = profile.get("sizes")
        image_size = _validate_image_size(
            profile.get("image_size", default_size),
            f"{source_root / config_name}: effective image_size for {source.name}",
        )

        variants = sizes if sizes is not None else [None]
        for size_name in variants:
            suffix = f"-{size_name}" if size_name is not None else ""
            output = output_dir / f"{_slug(source.stem)}{suffix}{extension}"
            definitions = (
                [f'size="{size_name}"'] if size_name is not None else []
            )
            targets.append(
                {
                    "source": source,
                    "output": output,
                    "image_size": image_size,
                    "definitions": definitions,
                }
            )

    return targets


def _explicit_targets(
    context: ProjectContext,
    default_image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    for build in context.config.get("builds", []) or []:
        output = context.path(build["output"])
        targets.append(
            {
                "source": context.path(build["source"]),
                "output": output,
                "image_size": _validate_image_size(
                    build.get("size", default_image_size),
                    f"build {build.get('name', output.name)!r}.size",
                ),
                "definitions": [],
            }
        )

    return targets


def _build_targets(
    context: ProjectContext,
    default_image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    paths = context.config.get("paths", {}) or {}
    targets: list[dict[str, Any]] = []

    render_root = paths.get("render_root")
    if render_root:
        targets.extend(
            _directory_targets(
                context,
                kind="render",
                source_root_value=str(render_root),
                default_image_size=default_image_size,
            )
        )

    export_root = paths.get("export_root")
    if export_root:
        targets.extend(
            _directory_targets(
                context,
                kind="export",
                source_root_value=str(export_root),
                default_image_size=default_image_size,
            )
        )

    # Legacy/exception entries remain supported. An explicit output overrides
    # the convention-generated target for the same path.
    by_output: dict[Path, dict[str, Any]] = {
        target["output"]: target for target in targets
    }
    for target in _explicit_targets(context, default_image_size):
        by_output[target["output"]] = target

    return list(by_output.values())


def build_project(context: ProjectContext) -> None:
    """Build configured directory entrypoints and legacy explicit entries."""

    osc = context.config.get("openscad", {}) or {}
    common = [str(v) for v in osc.get("common_flags", [])]
    render_flags = [str(v) for v in osc.get("render_flags", ["--render"])]
    default_image_size = _validate_image_size(
        osc.get("image_size", [1600, 1000]),
        "openscad.image_size",
    )
    watermark_text = _watermark_text(context)

    for target in _build_targets(context, default_image_size):
        source: Path = target["source"]
        output: Path = target["output"]
        definitions = [
            item
            for definition in target.get("definitions", [])
            for item in ("-D", definition)
        ]

        output.parent.mkdir(parents=True, exist_ok=True)

        if output.suffix.lower() == ".png":
            size = target["image_size"]
            render_output = _raw_png_path(output) if watermark_text else output

            if render_output.exists():
                render_output.unlink()
            if watermark_text and output.exists():
                output.unlink()

            try:
                args = [
                    "xvfb-run", "-a", "openscad",
                    *common, *render_flags, *definitions,
                    "--autocenter", "--viewall",
                    f"--imgsize={int(size[0])},{int(size[1])}",
                    "-o", str(render_output), str(source),
                ]
                run_checked(args, cwd=context.root)
                _require_output(render_output)

                if watermark_text:
                    run_checked(
                        [
                            "scad-image-watermark",
                            str(render_output),
                            str(output),
                            "--text",
                            watermark_text,
                        ],
                        cwd=context.root,
                    )
                    _require_output(output)
            finally:
                if render_output != output:
                    render_output.unlink(missing_ok=True)

        elif output.suffix.lower() == ".stl":
            if output.exists():
                output.unlink()
            args = [
                "openscad",
                *common,
                *definitions,
                "-o", str(output), str(source),
            ]
            run_checked(args, cwd=context.root)
            _require_output(output)
        else:
            raise RuntimeError(f"Unsupported build output: {output}")
