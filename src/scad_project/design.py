"""Generate design documentation using OpenSCAD or PythonSCAD render backends.

Source ``design.md`` files remain authoritative and are never modified.
``scad-render-defaults`` and ``scad-render`` describe render intent; the render
engine is selected explicitly when needed or inferred from the source suffix.

Supported engines:
- ``openscad``
- ``pythonscad``

Inference:
- ``.scad`` -> OpenSCAD
- ``.py``   -> PythonSCAD

An explicit ``engine`` always wins over suffix inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import yaml

from .build import _raw_png_path, _require_output, _watermark_text
from .config import ProjectContext
from .externals import configured_externals
from .process import run_checked


RENDER_BLOCK_RE = re.compile(
    r"<!--\s*(?P<tag>scad-render|scad-design)\s*\n(?P<body>.*?)\n\s*-->",
    re.DOTALL,
)
DEFAULTS_BLOCK_RE = re.compile(
    r"<!--\s*(?P<tag>scad-render-defaults|scad-design-defaults)\s*\n"
    r"(?P<body>.*?)\n\s*-->",
    re.DOTALL,
)
FENCE_RE = re.compile(
    r"\s*```openscad\s*\n(?P<code>.*?)\n```",
    re.DOTALL,
)
IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\((?P<target>img/[^)]+)\)")


@dataclass(frozen=True)
class DesignDocument:
    """One design source and its generated destination namespace."""

    source_file: Path
    scope: str
    relative_path: Path
    external_name: str | None = None


@dataclass(frozen=True)
class DesignRender:
    """One normalized render declaration."""

    document: DesignDocument
    block_start: int
    block_end: int
    engine: str
    kind: str
    image: str
    alt: str
    source: Path | None
    module: str | None
    view: Any
    inline_code: str | None
    vpr: list[float] | None
    vpt: list[float] | None
    vpd: float | None
    size: list[int] | None


def _project_design_roots(context: ProjectContext) -> list[Path]:
    """Return configured project design roots with backward compatibility."""

    paths = context.config["paths"]
    configured = paths.get("design_roots")
    if configured:
        return [context.path(item) for item in configured]
    return [context.path(paths["design_root"])]


def _inside(path: Path, parent: Path) -> bool:
    """Return whether path is located below parent."""

    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def discover_design_documents(context: ProjectContext) -> list[DesignDocument]:
    """Discover project and external ``design/design.md`` files.

    Configured external checkouts are excluded from project discovery and are
    added separately so generated paths retain the external repository name.
    """

    documents: list[DesignDocument] = []
    project_roots = _project_design_roots(context)
    external_roots = [
        external.root(context).resolve()
        for external in configured_externals(context)
    ]

    for design_root in project_roots:
        if not design_root.exists():
            continue

        for path in sorted(design_root.rglob("design/design.md")):
            resolved = path.resolve()
            if any(_inside(resolved, external_root) for external_root in external_roots):
                continue

            documents.append(
                DesignDocument(
                    source_file=resolved,
                    scope="project",
                    relative_path=resolved.relative_to(design_root.resolve()),
                )
            )

    for external in configured_externals(context):
        root = external.root(context)
        if not root.exists():
            continue

        for path in sorted(root.rglob("design/design.md")):
            documents.append(
                DesignDocument(
                    source_file=path.resolve(),
                    scope="external",
                    external_name=external.name,
                    relative_path=path.resolve().relative_to(root.resolve()),
                )
            )

    return documents


def _load_yaml_mapping(body: str, prefix: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a YAML metadata block and require a mapping."""

    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as exc:
        return None, f"{prefix}: invalid YAML: {exc}"
    if not isinstance(data, dict):
        return None, f"{prefix}: declaration must be a YAML mapping"
    return data, None


def _document_defaults(text: str, path: Path) -> tuple[dict[str, Any], list[str]]:
    """Return the optional document-level render defaults."""

    matches = list(DEFAULTS_BLOCK_RE.finditer(text))
    if len(matches) > 1:
        return {}, [f"{path}: only one scad-render-defaults block is allowed"]
    if not matches:
        return {}, []
    data, error = _load_yaml_mapping(
        matches[0].group("body"),
        f"{path}: render defaults",
    )
    return (data or {}), ([error] if error else [])


def _number_list(
    value: Any,
    *,
    length: int,
    field: str,
    error_prefix: str,
) -> tuple[list[float] | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, list) or len(value) != length or not all(
        isinstance(item, (int, float)) for item in value
    ):
        return None, f"{error_prefix}: {field} must contain {length} numbers"
    return [float(item) for item in value], None


def _image_size(value: Any, *, error_prefix: str) -> tuple[list[int] | None, str | None]:
    if value is None:
        return None, None
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, int) and item > 0 for item in value)
    ):
        return None, f"{error_prefix}: size must be [positive_width, positive_height]"
    return list(value), None


def _slug(value: Any, fallback: str) -> str:
    text = str(value).strip().lower() if value is not None else fallback
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def _infer_engine(source: Path | None) -> str | None:
    """Infer a render engine from an entrypoint suffix."""

    if source is None:
        return None
    suffix = source.suffix.lower()
    if suffix == ".scad":
        return "openscad"
    if suffix == ".py":
        return "pythonscad"
    return None


def _resolve_source(
    design_file: Path,
    source_value: Any,
    explicit_engine: str | None,
) -> Path | None:
    """Resolve an explicit or inferable render entrypoint.

    If source is omitted, a single sibling source matching the explicit engine
    is preferred. Without an explicit engine, inference is allowed only when
    exactly one ``.scad`` or ``.py`` candidate exists.
    """

    component_dir = design_file.parent.parent

    if source_value:
        return (component_dir / str(source_value)).resolve()

    suffixes: tuple[str, ...]
    if explicit_engine == "openscad":
        suffixes = (".scad",)
    elif explicit_engine == "pythonscad":
        suffixes = (".py",)
    else:
        suffixes = (".scad", ".py")

    candidates = sorted(
        path.resolve()
        for path in component_dir.iterdir()
        if path.is_file() and path.suffix.lower() in suffixes
    )
    return candidates[0] if len(candidates) == 1 else None


def parse_design_document(document: DesignDocument) -> tuple[list[DesignRender], list[str]]:
    """Parse and normalize render metadata for one design document."""

    path = document.source_file
    text = path.read_text(encoding="utf-8")
    defaults, errors = _document_defaults(text, path)
    renders: list[DesignRender] = []
    seen_images: set[str] = set()

    for idx, match in enumerate(RENDER_BLOCK_RE.finditer(text), 1):
        prefix = f"{path}: render {idx}"
        local, error = _load_yaml_mapping(match.group("body"), prefix)
        if error:
            errors.append(error)
            continue
        assert local is not None

        data = {**defaults, **local}
        kind = data.get("type", "source-view")
        view = data.get("view")

        if kind not in {"source-view", "inline"}:
            errors.append(f"{prefix}: unknown type {kind!r}")
            continue

        explicit_engine = data.get("engine")
        if explicit_engine is not None:
            if explicit_engine not in {"openscad", "pythonscad"}:
                errors.append(
                    f"{prefix}: engine must be 'openscad' or 'pythonscad'"
                )
                continue

        source = None
        inline_code = None

        if kind == "source-view":
            source = _resolve_source(path, data.get("source"), explicit_engine)
            if source is None or not source.is_file():
                errors.append(
                    f"{prefix}: source could not be resolved; specify source "
                    "when multiple candidate entrypoints exist"
                )
                continue
        else:
            # Inline rendering currently means inline OpenSCAD. A PythonSCAD
            # inline format can be added later without changing source-view API.
            if explicit_engine == "pythonscad":
                errors.append(
                    f"{prefix}: inline PythonSCAD renders are not supported; "
                    "use a .py source entrypoint"
                )
                continue
            fence = FENCE_RE.match(text[match.end():])
            if not fence:
                errors.append(
                    f"{prefix}: inline render must be immediately followed by "
                    "an openscad fenced block"
                )
                continue
            inline_code = fence.group("code")

        engine = explicit_engine or _infer_engine(source)
        if engine is None:
            engine = "openscad" if kind == "inline" else None
        if engine not in {"openscad", "pythonscad"}:
            errors.append(
                f"{prefix}: render engine is ambiguous; set engine explicitly"
            )
            continue

        module = data.get("module")
        if engine == "openscad" and kind == "source-view":
            if not isinstance(module, str) or not module.strip():
                errors.append(
                    f"{prefix}: OpenSCAD source-view requires module "
                    "(usually set it in scad-render-defaults)"
                )
                continue

        image = data.get("image")
        if image is None:
            image = f"{idx:02d}-{_slug(view, kind)}.png"
        if not isinstance(image, str) or not image.endswith(".png"):
            errors.append(f"{prefix}: image must end in .png")
            continue
        if "/" in image or "\\" in image:
            errors.append(f"{prefix}: image must be a filename")
            continue
        if image in seen_images:
            errors.append(f"{path}: duplicate image {image}")
            continue
        seen_images.add(image)

        alt = data.get("alt")
        if not isinstance(alt, str) or not alt.strip():
            label = view if isinstance(view, str) and view.strip() else Path(image).stem
            alt = str(label).replace("-", " ").replace("_", " ").strip().title()

        vpr, error = _number_list(
            data.get("vpr"), length=3, field="vpr", error_prefix=prefix
        )
        if error:
            errors.append(error)
            continue
        vpt, error = _number_list(
            data.get("vpt"), length=3, field="vpt", error_prefix=prefix
        )
        if error:
            errors.append(error)
            continue
        size, error = _image_size(data.get("size"), error_prefix=prefix)
        if error:
            errors.append(error)
            continue

        vpd_value = data.get("vpd")
        if vpd_value is not None and not isinstance(vpd_value, (int, float)):
            errors.append(f"{prefix}: vpd must be a number")
            continue
        vpd = float(vpd_value) if vpd_value is not None else None

        if (vpt is not None or vpd is not None) and not (
            vpr is not None and vpt is not None and vpd is not None
        ):
            errors.append(
                f"{prefix}: use either vpr alone for auto-fit, or provide "
                "vpr, vpt and vpd together"
            )
            continue

        renders.append(
            DesignRender(
                document=document,
                block_start=match.start(),
                block_end=match.end(),
                engine=engine,
                kind=kind,
                image=image,
                alt=alt,
                source=source,
                module=module if isinstance(module, str) else None,
                view=view,
                inline_code=inline_code,
                vpr=vpr,
                vpt=vpt,
                vpd=vpd,
                size=size,
            )
        )

    return renders, errors


def lint_design(context: ProjectContext) -> tuple[list[DesignRender], list[str]]:
    all_renders: list[DesignRender] = []
    errors: list[str] = []
    for document in discover_design_documents(context):
        renders, doc_errors = parse_design_document(document)
        all_renders.extend(renders)
        errors.extend(doc_errors)
    return all_renders, errors


def _lit(value: Any) -> str:
    """Serialize values for OpenSCAD/PythonSCAD ``-D`` expressions."""

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


def _openscad_entrypoint(render: DesignRender) -> str:
    """Create one temporary OpenSCAD entrypoint."""

    lines: list[str] = []
    if render.kind == "source-view":
        assert render.source is not None
        lines.append(f"use <{render.source.as_posix()}>")

    lines.append("$fn = 120;")

    if render.kind == "source-view":
        assert render.module is not None
        if render.view is None:
            lines.append(f"{render.module}();")
        else:
            lines.append(f"{render.module}(view = {_lit(render.view)});")
    else:
        lines.append(render.inline_code or "")

    return "\n".join(lines) + "\n"


def _camera_args(render: DesignRender) -> list[str]:
    """Return camera flags shared by the OpenSCAD-compatible CLIs."""

    if render.vpr is None:
        return ["--autocenter", "--viewall"]

    if render.vpt is None and render.vpd is None:
        camera = [0.0, 0.0, 0.0, *render.vpr, 0.0]
        return [
            "--camera=" + ",".join(str(v) for v in camera),
            "--autocenter",
            "--viewall",
        ]

    assert render.vpt is not None and render.vpd is not None
    camera = [*render.vpt, *render.vpr, render.vpd]
    return ["--camera=" + ",".join(str(v) for v in camera)]


def _engine_config(context: ProjectContext, engine: str) -> dict[str, Any]:
    """Return per-engine project configuration with safe defaults."""

    cfg = context.config.get(engine, {}) or {}
    if engine == "openscad":
        return {
            "common_flags": [str(v) for v in cfg.get("common_flags", [])],
            "render_flags": [str(v) for v in cfg.get("render_flags", ["--render"])],
        }

    return {
        "common_flags": [
            str(v) for v in cfg.get("common_flags", ["--trust-python"])
        ],
        "render_flags": [str(v) for v in cfg.get("render_flags", ["--render"])],
    }


def _render_args(
    context: ProjectContext,
    render: DesignRender,
    entry: Path | None,
    output: Path,
    size: list[int],
) -> list[str]:
    """Build the command line for one render backend."""

    cfg = _engine_config(context, render.engine)
    shared = [
        *cfg["common_flags"],
        *cfg["render_flags"],
        *_camera_args(render),
        f"--imgsize={int(size[0])},{int(size[1])}",
    ]

    if render.engine == "openscad":
        assert entry is not None
        return [
            "xvfb-run",
            "-a",
            "openscad",
            *shared,
            "-o",
            str(output),
            str(entry),
        ]

    assert render.source is not None
    args = [
        "xvfb-run",
        "-a",
        "pythonscad",
        *shared,
        "--trust-python",
    ]

    # Avoid duplicating --trust-python when it is already configured.
    deduped: list[str] = []
    for value in args:
        if value == "--trust-python" and value in deduped:
            continue
        deduped.append(value)

    if render.view is not None:
        deduped += ["-D", f"design_view={_lit(render.view)}"]

    deduped += ["-o", str(output), str(render.source)]
    return deduped


def _copy_source_assets(document: DesignDocument, out_doc: Path) -> None:
    """Copy static sibling assets used by legacy design documentation."""

    source_dir = document.source_file.parent
    target_dir = out_doc.parent
    for item in source_dir.iterdir():
        if item.name == document.source_file.name:
            continue
        destination = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _generate_markdown(source_text: str, renders: list[DesignRender]) -> str:
    """Generate reader-facing Markdown with ordinary image links."""

    replacements: list[tuple[int, int, str]] = []
    for match in DEFAULTS_BLOCK_RE.finditer(source_text):
        replacements.append((match.start(), match.end(), ""))

    for render in renders:
        replacements.append(
            (
                render.block_start,
                render.block_end,
                f"![{render.alt}](img/{render.image})",
            )
        )

    result = source_text
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _missing_local_images(markdown: str, document_path: Path) -> list[Path]:
    missing: list[Path] = []
    for match in IMAGE_LINK_RE.finditer(markdown):
        target = (document_path.parent / match.group("target")).resolve()
        if not target.is_file():
            missing.append(target)
    return missing


def build_design(context: ProjectContext) -> None:
    """Generate project and external design documentation."""

    renders, errors = lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    documents = discover_design_documents(context)
    by_document: dict[Path, list[DesignRender]] = {
        doc.source_file: [] for doc in documents
    }
    for render in renders:
        by_document.setdefault(render.document.source_file, []).append(render)

    openscad_cfg = context.config.get("openscad", {}) or {}
    default_size = openscad_cfg.get(
        "design_image_size",
        openscad_cfg.get("image_size", [640, 480]),
    )
    watermark_text = _watermark_text(context)

    build_root = context.path(context.config["paths"]["build_root"])
    generated_root = build_root / "design"
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="scad-project-design-build-") as td:
        stage = Path(td) / "design"
        stage.mkdir(parents=True, exist_ok=True)
        entry_root = Path(td) / "entrypoints"
        entry_root.mkdir(parents=True, exist_ok=True)
        entry_counter = 0

        for document in documents:
            if document.scope == "project":
                out_doc = stage / "project" / document.relative_path
            else:
                assert document.external_name
                out_doc = (
                    stage
                    / "ext"
                    / document.external_name
                    / document.relative_path
                )

            out_doc.parent.mkdir(parents=True, exist_ok=True)
            _copy_source_assets(document, out_doc)
            image_dir = out_doc.parent / "img"
            image_dir.mkdir(parents=True, exist_ok=True)

            doc_renders = by_document.get(document.source_file, [])
            for render in doc_renders:
                entry: Path | None = None
                if render.engine == "openscad":
                    entry_counter += 1
                    entry = entry_root / f"render-{entry_counter:04d}.scad"
                    entry.write_text(
                        _openscad_entrypoint(render),
                        encoding="utf-8",
                    )

                size = render.size or default_size
                output = image_dir / render.image
                render_output = _raw_png_path(output) if watermark_text else output
                if render_output.exists():
                    render_output.unlink()
                if watermark_text and output.exists():
                    output.unlink()

                args = _render_args(
                    context,
                    render,
                    entry,
                    render_output,
                    size,
                )

                # Run from the Python source directory for PythonSCAD so local
                # sibling imports behave exactly as they do in hand-written
                # PythonSCAD render scripts.
                cwd = (
                    render.source.parent
                    if render.engine == "pythonscad" and render.source is not None
                    else context.root
                )

                try:
                    run_checked(args, cwd=cwd)
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

            source_text = document.source_file.read_text(encoding="utf-8")
            generated = _generate_markdown(source_text, doc_renders)
            out_doc.write_text(generated, encoding="utf-8")

            missing = _missing_local_images(generated, out_doc)
            if missing:
                relative = ", ".join(
                    str(path.relative_to(stage)) for path in missing
                )
                message = (
                    f"{document.source_file}: missing generated image(s): "
                    f"{relative}"
                )
                if document.scope == "project":
                    raise RuntimeError(message)
                warnings.append(message)

        lines = [
            "# Design documentation",
            "",
            "Generated from source `design.md` files.",
            "",
            "## Project",
            "",
        ]

        project_docs = [d for d in documents if d.scope == "project"]
        if project_docs:
            for document in project_docs:
                link = Path("project") / document.relative_path
                lines.append(
                    f"- [{document.relative_path.as_posix()}]"
                    f"({link.as_posix()})"
                )
        else:
            lines.append("- No project design documents found.")

        lines += ["", "## Externals", ""]
        external_docs = [d for d in documents if d.scope == "external"]
        if external_docs:
            for document in external_docs:
                link = Path("ext") / document.external_name / document.relative_path
                label = (
                    f"{document.external_name}: "
                    f"{document.relative_path.as_posix()}"
                )
                lines.append(f"- [{label}]({link.as_posix()})")
        else:
            lines.append("- No external design documents found.")

        (stage / "README.md").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

        if generated_root.exists():
            shutil.rmtree(generated_root)
        generated_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, generated_root)

    for warning in warnings:
        print(f"WARNING: {warning}")

    print(
        "Generated design documentation: "
        f"{generated_root.relative_to(context.root)}"
    )
