"""Build materialized design documentation from Markdown render declarations.

Source ``design.md`` files remain authoritative and are never modified.  This
module discovers design documents in the project and configured externals,
renders declared OpenSCAD views, and creates a self-contained documentation
copy below ``bld/design``.
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


# A design declaration is YAML embedded in a Markdown comment.  Keeping the
# declaration in Markdown means the source document stays readable in Git.
BLOCK_RE = re.compile(
    r"<!--\s*scad-design\s*\n(?P<body>.*?)\n\s*-->",
    re.DOTALL,
)
FENCE_RE = re.compile(
    r"\s*```openscad\s*\n(?P<code>.*?)\n```",
    re.DOTALL,
)
IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\((?P<target>img/[^)]+)\)")


@dataclass(frozen=True)
class DesignDocument:
    """One source design document and its destination namespace."""

    source_file: Path
    scope: str
    relative_path: Path
    external_name: str | None = None


@dataclass(frozen=True)
class DesignRender:
    """Normalized render declaration parsed from a design document."""

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
    """Return project and external ``design/design.md`` sources.

    The project search deliberately skips ``dsg/openscad/ext`` because those
    files are discovered a second time through the configured external list.
    That preserves the external name in the generated destination path.
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

    # Externals are read-only inputs.  Materialization must never write into
    # their checkout; all generated output is routed to bld/design/ext/....
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
    """Infer the component SCAD file when exactly one candidate exists."""

    candidates = sorted(design_file.parent.parent.glob("*.scad"))
    return candidates[0].resolve() if len(candidates) == 1 else None


def _number_list(value: Any, *, length: int, field: str, error_prefix: str) -> tuple[list[float] | None, str | None]:
    """Validate a numeric YAML list used by viewport metadata."""

    if value is None:
        return None, None
    if not isinstance(value, list) or len(value) != length or not all(
        isinstance(item, (int, float)) for item in value
    ):
        return None, f"{error_prefix}: {field} must contain {length} numbers"
    return [float(item) for item in value], None


def _image_size(value: Any, *, error_prefix: str) -> tuple[list[int] | None, str | None]:
    """Validate optional ``size: [width, height]`` metadata."""

    if value is None:
        return None, None
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, int) and item > 0 for item in value)
    ):
        return None, f"{error_prefix}: size must be [positive_width, positive_height]"
    return list(value), None


def parse_design_document(document: DesignDocument) -> tuple[list[DesignRender], list[str]]:
    """Parse and validate all ``scad-design`` declarations in one document."""

    path = document.source_file
    text = path.read_text(encoding="utf-8")
    renders: list[DesignRender] = []
    errors: list[str] = []
    seen_images: set[str] = set()

    for idx, match in enumerate(BLOCK_RE.finditer(text), 1):
        prefix = f"{path}: block {idx}"
        try:
            data = yaml.safe_load(match.group("body")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{prefix}: invalid YAML: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"{prefix}: declaration must be a YAML mapping")
            continue

        kind = data.get("type")
        image = data.get("image")

        if kind not in {"source-view", "inline"}:
            errors.append(f"{prefix}: unknown type {kind!r}")
            continue
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
            alt = Path(image).stem.replace("-", " ").replace("_", " ").strip().title()

        vpr, error = _number_list(data.get("vpr"), length=3, field="vpr", error_prefix=prefix)
        if error:
            errors.append(error)
            continue
        vpt, error = _number_list(data.get("vpt"), length=3, field="vpt", error_prefix=prefix)
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

        # Exact camera mode requires all three viewport values.  A declaration
        # with only vpr is intentionally supported as "orientation + auto-fit".
        if (vpt is not None or vpd is not None) and not (vpr is not None and vpt is not None and vpd is not None):
            errors.append(
                f"{prefix}: use either vpr alone for auto-fit, or provide vpr, vpt and vpd together"
            )
            continue

        source = None
        module = None
        inline_code = None

        if kind == "source-view":
            module = data.get("module")
            if not isinstance(module, str) or not module.strip():
                errors.append(f"{prefix}: source-view requires module")
                continue

            source_value = data.get("source")
            if source_value:
                source = (path.parent.parent / str(source_value)).resolve()
            else:
                source = _infer_source(path)

            if source is None or not source.is_file():
                errors.append(
                    f"{prefix}: source could not be resolved; specify source explicitly when multiple .scad files exist"
                )
                continue
        else:
            fence = FENCE_RE.match(text[match.end():])
            if not fence:
                errors.append(
                    f"{prefix}: inline render must be immediately followed by an openscad fenced block"
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
                view=data.get("view"),
                inline_code=inline_code,
                vpr=vpr,
                vpt=vpt,
                vpd=vpd,
                size=size,
            )
        )

    return renders, errors


def lint_design(context: ProjectContext) -> tuple[list[DesignRender], list[str]]:
    """Lint all project and external design declarations."""

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
    """Create the temporary SCAD entrypoint for one declared design view."""

    lines: list[str] = []
    if render.kind == "source-view":
        assert render.source is not None
        # Absolute source paths keep the temporary entrypoint independent of
        # its staging directory while relative imports inside the source file
        # continue to resolve from that source file.
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
    """Return OpenSCAD camera flags without disabling automatic framing.

    Writing ``$vpr`` into a SCAD entrypoint disables OpenSCAD's view-all and
    autocenter behavior, which made earlier design images appear severely
    zoomed/cropped.  Passing camera orientation on the command line lets us use
    ``--viewall --autocenter`` when only ``vpr`` is supplied.
    """

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


def _materialized_document_path(context: ProjectContext, document: DesignDocument) -> Path:
    """Map a source document to its stable path below ``bld/design``."""

    root = context.path(context.config["paths"]["build_root"]) / "design"
    if document.scope == "project":
        return root / "project" / document.relative_path
    assert document.external_name
    return root / "ext" / document.external_name / document.relative_path


def _copy_source_assets(document: DesignDocument, out_doc: Path) -> None:
    """Copy non-Markdown design assets before generated renders are written.

    This keeps materialized documentation compatible with existing libraries
    that still reference checked-in images or other static assets.  Generated
    render declarations remain authoritative and overwrite same-named files.
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


def _materialize_markdown(source_text: str, renders: list[DesignRender]) -> str:
    """Replace render declarations by image references in the generated copy."""

    result = source_text
    # Replace from the end of the file so stored source offsets remain valid.
    for render in sorted(renders, key=lambda item: item.block_start, reverse=True):
        replacement = f"![{render.alt}](img/{render.image})"
        result = result[:render.block_start] + replacement + result[render.block_end:]
    return result


def _missing_local_images(markdown: str, document_path: Path) -> list[Path]:
    """Return missing local ``img/...`` links from a materialized document."""

    missing: list[Path] = []
    for match in IMAGE_LINK_RE.finditer(markdown):
        target = (document_path.parent / match.group("target")).resolve()
        if not target.is_file():
            missing.append(target)
    return missing


def build_design(context: ProjectContext) -> None:
    """Build a complete, browsable design-documentation snapshot."""

    renders, errors = lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    documents = discover_design_documents(context)
    by_document: dict[Path, list[DesignRender]] = {doc.source_file: [] for doc in documents}
    for render in renders:
        by_document.setdefault(render.document.source_file, []).append(render)

    openscad = context.config.get("openscad", {}) or {}
    common_flags = [str(v) for v in openscad.get("common_flags", [])]
    render_flags = [str(v) for v in openscad.get("render_flags", ["--render"])]
    default_size = openscad.get("image_size", [1600, 1000])

    build_root = context.path(context.config["paths"]["build_root"])
    materialized_root = build_root / "design"
    warnings: list[str] = []

    # Stage the whole tree first.  A failed render therefore leaves the user's
    # previous bld/design snapshot intact instead of half-updating it.
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
                out_doc = stage / "ext" / document.external_name / document.relative_path

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
                    "xvfb-run", "-a", "openscad",
                    *common_flags,
                    *render_flags,
                    *_camera_args(render),
                    f"--imgsize={int(size[0])},{int(size[1])}",
                    "-o", str(output), str(entry),
                ]
                run_checked(args, cwd=context.root)
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f"Missing or empty design render: {output}")

            source_text = document.source_file.read_text(encoding="utf-8")
            materialized = _materialize_markdown(source_text, doc_renders)
            out_doc.write_text(materialized, encoding="utf-8")

            # Legacy external docs can contain image links without scad-design
            # declarations.  Copy source assets when they exist, but warn when
            # a dependency itself ships a broken legacy reference.  Project
            # documents are stricter because the project owns those sources.
            missing = _missing_local_images(materialized, out_doc)
            if missing:
                relative = ", ".join(str(path.relative_to(stage)) for path in missing)
                message = f"{document.source_file}: missing materialized image(s): {relative}"
                if document.scope == "project":
                    raise RuntimeError(message)
                warnings.append(message)

        lines = [
            "# Design documentation",
            "",
            "Generated from source `design.md` files. Images live next to the materialized documents.",
            "",
            "## Project",
            "",
        ]
        project_docs = [d for d in documents if d.scope == "project"]
        if project_docs:
            for document in project_docs:
                link = Path("project") / document.relative_path
                lines.append(f"- [{document.relative_path.as_posix()}]({link.as_posix()})")
        else:
            lines.append("- No project design documents found.")

        lines += ["", "## Externals", ""]
        external_docs = [d for d in documents if d.scope == "external"]
        if external_docs:
            for document in external_docs:
                link = Path("ext") / document.external_name / document.relative_path
                label = f"{document.external_name}: {document.relative_path.as_posix()}"
                lines.append(f"- [{label}]({link.as_posix()})")
        else:
            lines.append("- No external design documents found.")

        (stage / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        if materialized_root.exists():
            shutil.rmtree(materialized_root)
        materialized_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, materialized_root)

    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"Materialized design documentation: {materialized_root.relative_to(context.root)}")
