"""SCons-side driver for selective design image rendering."""

from __future__ import annotations

import json
from pathlib import Path

from SCons.Script import ARGUMENTS, CacheDir, Command, Default, Depends, SConsignFile, Value

from scad_project.build import _require_output
from scad_project.process import run_checked


def _project_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _execute_target(spec: dict, root: Path, execution_log: Path) -> int:
    output = _project_path(root, spec["output"])
    render_output = _project_path(root, spec.get("render_output", spec["output"]))
    watermark_text = spec.get("watermark_text")
    cwd = _project_path(root, spec["cwd"])
    command = [str(value) for value in spec["command"]]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    if render_output != output:
        render_output.unlink(missing_ok=True)

    try:
        run_checked(command, cwd=cwd)
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

    execution_log.parent.mkdir(parents=True, exist_ok=True)
    with execution_log.open("a", encoding="utf-8") as handle:
        handle.write(spec["output"] + "\n")

    print(f"SCons design built: {output.relative_to(root)}")
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

nodes = []
for spec in manifest["targets"]:
    source_nodes = [
        str(_project_path(project_root, value))
        for value in spec.get("dependencies", [])
    ]
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
