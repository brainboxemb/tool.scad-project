"""SCons-side driver for the experimental selective OpenSCAD build backend."""

from __future__ import annotations

import json
from pathlib import Path

from SCons.Script import ARGUMENTS, CacheDir, Command, Default, Depends, SConsignFile, Value

from scad_project.build import _raw_png_path, _require_output
from scad_project.openscad_deps import scan_openscad_dependencies
from scad_project.process import run_checked


def _project_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _execute_target(spec: dict, root: Path, execution_log: Path) -> int:
    source = _project_path(root, spec["source"])
    output = _project_path(root, spec["output"])
    common = [str(value) for value in spec.get("common_flags", [])]
    render_flags = [str(value) for value in spec.get("render_flags", ["--render"])]
    definitions = [
        item
        for definition in spec.get("definitions", [])
        for item in ("-D", str(definition))
    ]
    watermark_text = spec.get("watermark_text")

    output.parent.mkdir(parents=True, exist_ok=True)

    if output.suffix.lower() == ".png":
        size = spec["image_size"]
        render_output = _raw_png_path(output) if watermark_text else output

        if render_output.exists():
            render_output.unlink()
        if watermark_text and output.exists():
            output.unlink()

        try:
            run_checked(
                [
                    "xvfb-run",
                    "-a",
                    "openscad",
                    *common,
                    *render_flags,
                    *definitions,
                    "--autocenter",
                    "--viewall",
                    f"--imgsize={int(size[0])},{int(size[1])}",
                    "-o",
                    str(render_output),
                    str(source),
                ],
                cwd=root,
            )
            _require_output(render_output)

            if watermark_text:
                run_checked(
                    [
                        "scad-image-watermark",
                        str(render_output),
                        str(output),
                        "--text",
                        str(watermark_text),
                    ],
                    cwd=root,
                )
                _require_output(output)
        finally:
            if render_output != output:
                render_output.unlink(missing_ok=True)

    elif output.suffix.lower() == ".stl":
        if output.exists():
            output.unlink()
        run_checked(
            [
                "openscad",
                *common,
                *definitions,
                "-o",
                str(output),
                str(source),
            ],
            cwd=root,
        )
        _require_output(output)
    else:
        raise RuntimeError(f"Unsupported build output: {output}")

    execution_log.parent.mkdir(parents=True, exist_ok=True)
    with execution_log.open("a", encoding="utf-8") as handle:
        handle.write(spec["output"] + "\n")

    print(f"SCons built: {output.relative_to(root)}")
    return 0


def _action(target, source, env) -> int:
    spec = json.loads(str(env["TARGET_SPEC"]))
    root = Path(str(env["PROJECT_ROOT"])).resolve()
    execution_log = Path(str(env["EXECUTION_LOG"])).resolve()
    return _execute_target(spec, root, execution_log)


manifest_path = Path(ARGUMENTS["SCAD_PROJECT_MANIFEST"]).resolve()
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
project_root = Path(manifest["project_root"]).resolve()

cache_root = Path(manifest["cache_root"]).resolve()
cache_root.mkdir(parents=True, exist_ok=True)
CacheDir(str(cache_root))

sconsign = Path(manifest["sconsign"]).resolve()
sconsign.parent.mkdir(parents=True, exist_ok=True)
SConsignFile(str(sconsign))

execution_log = Path(manifest["execution_log"]).resolve()
search_paths = [Path(value).resolve() for value in manifest.get("search_paths", [])]

nodes = []
for spec in manifest["targets"]:
    source_path = _project_path(project_root, spec["source"])
    dependencies = scan_openscad_dependencies(
        source_path,
        search_paths=search_paths,
    )
    source_nodes = [str(source_path), *[str(path) for path in dependencies]]
    spec_json = json.dumps(spec, sort_keys=True, separators=(",", ":"))

    target_node = Command(
        str(_project_path(project_root, spec["output"])),
        source_nodes,
        _action,
        TARGET_SPEC=spec_json,
        PROJECT_ROOT=str(project_root),
        EXECUTION_LOG=str(execution_log),
    )
    Depends(target_node, Value(spec_json))
    nodes.extend(target_node)

Default(nodes)
