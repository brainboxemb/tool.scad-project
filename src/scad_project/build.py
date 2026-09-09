"""Build configured OpenSCAD PNG and STL outputs."""

from __future__ import annotations

from pathlib import Path

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


def build_project(context: ProjectContext) -> None:
    """Execute the explicit ``builds`` entries from ``project.yml``."""

    osc = context.config.get("openscad", {}) or {}
    common = [str(v) for v in osc.get("common_flags", [])]
    render_flags = [str(v) for v in osc.get("render_flags", ["--render"])]
    image_size = osc.get("image_size", [1600, 1000])
    watermark_text = _watermark_text(context)

    for build in context.config.get("builds", []) or []:
        source = context.path(build["source"])
        output = context.path(build["output"])
        output.parent.mkdir(parents=True, exist_ok=True)

        if output.suffix.lower() == ".png":
            size = build.get("size", image_size)
            render_output = _raw_png_path(output) if watermark_text else output

            if render_output.exists():
                render_output.unlink()
            if watermark_text and output.exists():
                output.unlink()

            try:
                args = [
                    "xvfb-run", "-a", "openscad",
                    *common, *render_flags,
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
            args = ["openscad", *common, "-o", str(output), str(source)]
            run_checked(args, cwd=context.root)
            _require_output(output)
        else:
            raise RuntimeError(f"Unsupported build output: {output}")
