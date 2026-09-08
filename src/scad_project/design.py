from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import Any
import yaml

from .config import ProjectContext
from .process import run_checked

BLOCK_RE = re.compile(r"<!--\s*scad-design\s*\n(?P<body>.*?)\n\s*-->", re.DOTALL)
FENCE_RE = re.compile(r"\s*```openscad\s*\n(?P<code>.*?)\n```", re.DOTALL)


@dataclass(frozen=True)
class DesignRender:
    design_file: Path
    kind: str
    image: str
    source: Path | None
    module: str | None
    view: Any
    inline_code: str | None
    vpr: list | None
    vpt: list | None
    vpd: float | None
    size: list[int] | None

    @property
    def output(self) -> Path:
        return self.design_file.parent / "img" / self.image


def _infer_source(design_file: Path) -> Path | None:
    candidates = sorted(design_file.parent.parent.glob("*.scad"))
    return candidates[0].resolve() if len(candidates) == 1 else None


def parse_design_file(path: Path) -> tuple[list[DesignRender], list[str]]:
    text = path.read_text(encoding="utf-8")
    renders: list[DesignRender] = []
    errors: list[str] = []
    seen: set[str] = set()

    for idx, match in enumerate(BLOCK_RE.finditer(text), 1):
        try:
            data = yaml.safe_load(match.group("body")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path}: block {idx}: invalid YAML: {exc}")
            continue

        kind = data.get("type")
        image = data.get("image")

        if kind not in {"source-view", "inline"}:
            errors.append(f"{path}: block {idx}: unknown type")
            continue
        if not isinstance(image, str) or not image.endswith(".png"):
            errors.append(f"{path}: block {idx}: image must end in .png")
            continue
        if "/" in image or "\\" in image:
            errors.append(f"{path}: block {idx}: image must be a filename")
            continue
        if image in seen:
            errors.append(f"{path}: duplicate image {image}")
            continue
        seen.add(image)

        source = None
        module = None
        inline = None

        if kind == "source-view":
            module = data.get("module")
            if not module:
                errors.append(f"{path}: block {idx}: source-view requires module")
                continue
            source = (
                (path.parent.parent / data["source"]).resolve()
                if data.get("source")
                else _infer_source(path)
            )
            if source is None or not source.is_file():
                errors.append(f"{path}: block {idx}: source could not be resolved")
                continue
        else:
            fence = FENCE_RE.match(text[match.end():])
            if not fence:
                errors.append(
                    f"{path}: block {idx}: inline render must be immediately "
                    "followed by an openscad fenced block"
                )
                continue
            inline = fence.group("code")

        renders.append(
            DesignRender(
                path, kind, image, source, module, data.get("view"), inline,
                data.get("vpr"), data.get("vpt"),
                float(data["vpd"]) if data.get("vpd") is not None else None,
                data.get("size"),
            )
        )

    return renders, errors


def lint_design(context: ProjectContext):
    root = context.path(context.config["paths"]["design_root"])
    renders: list[DesignRender] = []
    errors: list[str] = []
    stale: list[Path] = []

    if not root.exists():
        return renders, errors, stale

    ext = (root / "ext").resolve()
    for design_file in sorted(root.rglob("design/design.md")):
        try:
            design_file.resolve().relative_to(ext)
            continue
        except ValueError:
            pass

        found, found_errors = parse_design_file(design_file)
        renders.extend(found)
        errors.extend(found_errors)

        expected = {r.output.resolve() for r in found}
        image_dir = design_file.parent / "img"
        if image_dir.exists():
            for png in image_dir.glob("*.png"):
                if png.resolve() not in expected:
                    stale.append(png)

    return renders, errors, stale


def _lit(value):
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_lit(v) for v in value) + "]"
    if value is None:
        return "undef"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _entrypoint(r: DesignRender) -> str:
    lines = []
    if r.kind == "source-view":
        lines.append(f"use <{r.source.as_posix()}>")
    lines.append("$fn = 120;")
    if r.vpr is not None:
        lines.append(f"$vpr = {_lit(r.vpr)};")
    if r.vpt is not None:
        lines.append(f"$vpt = {_lit(r.vpt)};")
    if r.vpd is not None:
        lines.append(f"$vpd = {_lit(r.vpd)};")

    if r.kind == "source-view":
        if r.view is None:
            lines.append(f"{r.module}();")
        else:
            lines.append(f"{r.module}(view = {_lit(r.view)});")
    else:
        lines.append(r.inline_code or "")

    return "\n".join(lines) + "\n"


def render_design(context: ProjectContext) -> None:
    renders, errors, stale = lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    osc = context.config.get("openscad", {}) or {}
    common = [str(v) for v in osc.get("common_flags", [])]
    render_flags = [str(v) for v in osc.get("render_flags", ["--render"])]
    default_size = osc.get("image_size", [1600, 1000])

    with tempfile.TemporaryDirectory(prefix="scad-project-") as td:
        for i, r in enumerate(renders, 1):
            r.output.parent.mkdir(parents=True, exist_ok=True)
            entry = Path(td) / f"design-{i:03d}.scad"
            entry.write_text(_entrypoint(r), encoding="utf-8")
            size = r.size or default_size
            run_checked(
                [
                    "xvfb-run", "-a", "openscad",
                    *common, *render_flags,
                    f"--imgsize={int(size[0])},{int(size[1])}",
                    "-o", str(r.output), str(entry),
                ],
                cwd=context.root,
            )
            if not r.output.is_file() or r.output.stat().st_size == 0:
                raise RuntimeError(f"Missing design render: {r.output}")

    for path in stale:
        print(f"Removing stale design image: {path.relative_to(context.root)}")
        path.unlink()
