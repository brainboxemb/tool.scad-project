"""Generate design documentation from Markdown render declarations.

Source ``design.md`` files remain authoritative and are never modified. This
module discovers project and external design documents, renders declared
OpenSCAD views, and writes a complete generated documentation tree below
``bld/design``.

Canonical Markdown tags are ``scad-render-defaults`` and ``scad-render``.
Legacy ``scad-design`` render tags remain supported while existing libraries
are migrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import yaml

from .config import ProjectContext
from .externals import configured_externals
from .process import run_checked


# Render metadata stays inside Markdown comments so source documentation remains
# readable in GitHub even before generated images have been built.
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
    """One source design document and its generated destination namespace."""

    source_file: Path
    scope: str
    relative_path: Path
    external_name: str | None = None


@dataclass(frozen=True)
class DesignRender:
    """One normalized render declaration after document defaults are applied."""

    document: DesignDocument
    block_start: int
    block_end: int
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


def discover_design_documents(context: ProjectContext) -> list[DesignDocument]:
    """Return project and configured-external ``design/design.md`` sources.

    Project discovery skips ``dsg/openscad/ext`` because configured externals
    are discovered separately. Keeping that distinction lets the generated tree
    preserve a stable ``ext/<external-name>/...`` namespace.
    """

    documents: list[DesignDocument] = []
    design_root = context.path(context.config["paths"]["design_root"])

    if design_root.exists():
        ext_root = (design_root / "ext").resolve()
        for path in sorted(design_root.rglob("design/design.md")):
            try:
                path.resolve().relative_to(ext_root)
                continue
            except ValueError:
                pass

            documents.append(
                DesignDocument(
                    source_file=path.resolve(),
                    scope="project",
                    relative_path=path.resolve().relative_to(design_root.resolve()),
                )
            )

    # External repositories are read-only inputs. Generated docs and images
    # always go to bld/design; dependency working trees are never modified.
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


def _infer_source(design_file: Path) -> Path | None:
    """Infer the component SCAD source when exactly one candidate exists."""

    candidates = sorted(design_file.parent.parent.glob("*.scad"))
    return candidates[0].resolve() if len(candidates) == 1 else None


def _load_yaml_mapping(body: str, prefix: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read one YAML comment body and require a mapping."""

    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as exc:
        return None, f"{prefix}: invalid YAML: {exc}"

    if not isinstance(data, dict):
        return None, f"{prefix}: declaration must be a YAML mapping"
    return data, None


def _document_defaults(text: str, path: Path) -> tuple[dict[str, Any], list[str]]:
    """Return the single optional render-defaults block from a document."""

    matches = list(DEFAULTS_BLOCK_RE.finditer(text))
    if len(matches) > 1:
        return {}, [f"{path}: only one scad-render-defaults block is allowed"]
    if not matches:
        return {}, []

    match = matches[0]
    data, error = _load_yaml_mapping(match.group("body"), f"{path}: render defaults")
    return (data or {}), ([error] if error else [])


def _number_list(
    value: Any,
    *,
    length: int,
    field: str,
    error_prefix: str,
) -> tuple[list[float] | None, str | None]:
    """Validate a numeric YAML list used by viewport metadata."""

    if value is None:
        return None, None
    if not isinstance(value, list) or len(value) != length or not all(
        isinstance(item, (int, float)) for item in value
    ):
        return None, f"{error_prefix}: {field} must contain {length} numbers"
    return [float(item) for item in value], None


def _image_size(
    value: Any,
    *,
    error_prefix: str,
) -> tuple[list[int] | None, str | None]:
    """Validate optional ``size: [width, height]`` render metadata."""

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
    """Create a stable, filename-safe suffix for automatic render names."""

    text = str(value).strip().lower() if value is not None else fallback
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def parse_design_document(document: DesignDocument) -> tuple[list[DesignRender], list[str]]:
    """Parse render declarations and apply document-level defaults.

    Precedence is:

    ``project.yml defaults -> scad-render-defaults -> scad-render``

    The project-level image-size default is applied later during rendering.
    Metadata in ``scad-render`` therefore only needs to contain values that
    differ for that individual design step.
    """

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

        # Per-render values override the defaults block. Source-view is the
        # normal case, so authors do not need to repeat the type on every step.
        data = {**defaults, **local}
        kind = data.get("type", "source-view")
        view = data.get("view")

        if kind not in {"source-view", "inline"}:
            errors.append(f"{prefix}: unknown type {kind!r}")
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

        # vpr by itself means "orient and auto-fit". Once vpt/vpd is supplied,
        # all exact-camera fields must be present to avoid ambiguous framing.
        if (vpt is not None or vpd is not None) and not (
            vpr is not None and vpt is not None and vpd is not None
        ):
            errors.append(
                f"{prefix}: use either vpr alone for auto-fit, or provide "
                "vpr, vpt and vpd together"
            )
            continue

        source = None
        module = None
        inline_code = None

        if kind == "source-view":
            module = data.get("module")
            if not isinstance(module, str) or not module.strip():
                errors.append(
                    f"{prefix}: source-view requires module "
                    "(usually set it once in scad-render-defaults)"
                )
                continue

            source_value = data.get("source")
            if source_value:
                source = (path.parent.parent / str(source_value)).resolve()
            else:
                source = _infer_source(path)

            if source is None or not source.is_file():
                errors.append(
                    f"{prefix}: source could not be resolved; specify source "
                    "when multiple .scad files exist"
                )
                continue
        else:
            fence = FENCE_RE.match(text[match.end():])
            if not fence:
                errors.append(
                    f"{prefix}: inline render must be immediately followed by "
                    "an openscad fenced block"
                )
                continue
            inline_code = fence.group("code")

        renders.append(
            DesignRender(
                document=document,
                block_start=match.start(),
                block_end=match.end(),
                kind=kind,
                image=image,
                alt=alt,
                source=source,
                module=module,
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
    """Lint all project and external design-render declarations."""

    all_renders: list[DesignRender] = []
    errors: list[str] = []
    for document in discover_design_documents(context):
        renders, doc_errors = parse_design_document(document)
        all_renders.extend(renders)
        errors.extend(doc_errors)
    return all_renders, errors


def _lit(value: Any) -> str:
    """Serialize the small subset of values used in generated SCAD calls."""

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


def _entrypoint(render: DesignRender) -> str:
    """Create the temporary SCAD entrypoint for one design render."""

    lines: list[str] = []
    if render.kind == "source-view":
        assert render.source is not None
        # Absolute source paths make the temporary entrypoint independent of
        # the staging directory. Includes inside that source remain relative to
        # the source file as OpenSCAD normally expects.
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
    """Return OpenSCAD camera flags while preserving useful auto-fit behavior."""

    if render.vpr is None:
        return ["--autocenter", "--viewall"]

    if render.vpt is None and render.vpd is None:
        # OpenSCAD's CLI camera form needs target and distance values too.
        # A zero distance combined with --viewall means vpr acts only as the
        # requested orientation and OpenSCAD determines a suitable framing.
        camera = [0.0, 0.0, 0.0, *render.vpr, 0.0]
        return [
            "--camera=" + ",".join(str(v) for v in camera),
            "--autocenter",
            "--viewall",
        ]

    assert render.vpt is not None and render.vpd is not None
    camera = [*render.vpt, *render.vpr, render.vpd]
    return ["--camera=" + ",".join(str(v) for v in camera)]


def _generated_document_path(
    context: ProjectContext,
    document: DesignDocument,
) -> Path:
    """Map one source document to its stable path below ``bld/design``."""

    root = context.path(context.config["paths"]["build_root"]) / "design"
    if document.scope == "project":
        return root / "project" / document.relative_path
    assert document.external_name
    return root / "ext" / document.external_name / document.relative_path


def _copy_source_assets(document: DesignDocument, out_doc: Path) -> None:
    """Copy static design assets before generated renders are written.

    This keeps generated documentation compatible with libraries that still
    reference checked-in images. Generated render declarations remain
    authoritative and overwrite files with the same names.
    """

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
    """Create the generated Markdown copy with real image references."""

    replacements: list[tuple[int, int, str]] = []

    # Render-default blocks are authoring metadata and should not appear in the
    # generated documentation shown to readers.
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

    # Work backwards so source offsets remain valid while replacing text.
    result = source_text
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _missing_local_images(markdown: str, document_path: Path) -> list[Path]:
    """Return missing local ``img/...`` links from generated Markdown."""

    missing: list[Path] = []
    for match in IMAGE_LINK_RE.finditer(markdown):
        target = (document_path.parent / match.group("target")).resolve()
        if not target.is_file():
            missing.append(target)
    return missing


def build_design(context: ProjectContext) -> None:
    """Generate the complete browsable design-documentation tree."""

    renders, errors = lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    documents = discover_design_documents(context)
    by_document: dict[Path, list[DesignRender]] = {
        doc.source_file: [] for doc in documents
    }
    for render in renders:
        by_document.setdefault(render.document.source_file, []).append(render)

    openscad = context.config.get("openscad", {}) or {}
    common_flags = [str(v) for v in openscad.get("common_flags", [])]
    render_flags = [str(v) for v in openscad.get("render_flags", ["--render"])]

    # Design docs use a deliberately modest default image size. Normal project
    # renders continue to use openscad.image_size.
    default_size = openscad.get(
        "design_image_size",
        openscad.get("image_size", [640, 480]),
    )

    build_root = context.path(context.config["paths"]["build_root"])
    generated_root = build_root / "design"
    warnings: list[str] = []

    # Build the complete tree in a temporary staging directory first. A failed
    # render therefore leaves the previous local bld/design untouched.
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
                entry_counter += 1
                entry = entry_root / f"render-{entry_counter:04d}.scad"
                entry.write_text(_entrypoint(render), encoding="utf-8")

                size = render.size or default_size
                output = image_dir / render.image
                args = [
                    "xvfb-run",
                    "-a",
                    "openscad",
                    *common_flags,
                    *render_flags,
                    *_camera_args(render),
                    f"--imgsize={int(size[0])},{int(size[1])}",
                    "-o",
                    str(output),
                    str(entry),
                ]
                run_checked(args, cwd=context.root)

                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f"Missing or empty design render: {output}")

            source_text = document.source_file.read_text(encoding="utf-8")
            generated = _generate_markdown(source_text, doc_renders)
            out_doc.write_text(generated, encoding="utf-8")

            # Legacy external docs can contain image links without render
            # declarations. Copy assets when available and warn when a
            # dependency itself contains a broken legacy link. Project-owned
            # documentation stays strict and fails on missing local images.
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
                link = (
                    Path("ext")
                    / document.external_name
                    / document.relative_path
                )
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
