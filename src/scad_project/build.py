from __future__ import annotations
from .config import ProjectContext
from .process import run_checked


def check_libraries(context: ProjectContext) -> list[str]:
    errors = []
    for lib in context.config.get("libraries", []) or []:
        required = context.path(lib["path"]) / lib["required_file"]
        if not required.is_file():
            errors.append(
                f"External library not initialized: "
                f"{required.relative_to(context.root)}"
            )
    return errors


def build_project(context: ProjectContext) -> None:
    osc = context.config.get("openscad", {}) or {}
    common = [str(v) for v in osc.get("common_flags", [])]
    render_flags = [str(v) for v in osc.get("render_flags", ["--render"])]
    image_size = osc.get("image_size", [1600, 1000])

    for build in context.config.get("builds", []) or []:
        source = context.path(build["source"])
        output = context.path(build["output"])
        output.parent.mkdir(parents=True, exist_ok=True)

        if output.suffix.lower() == ".png":
            size = build.get("size", image_size)
            args = [
                "xvfb-run", "-a", "openscad",
                *common, *render_flags,
                f"--imgsize={int(size[0])},{int(size[1])}",
                "-o", str(output), str(source),
            ]
        elif output.suffix.lower() == ".stl":
            args = ["openscad", *common, "-o", str(output), str(source)]
        else:
            raise RuntimeError(f"Unsupported build output: {output}")

        run_checked(args, cwd=context.root)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Missing build output: {output}")
