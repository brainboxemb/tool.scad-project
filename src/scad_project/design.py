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


BLOCK_RE = re.compile(
    r"<!--\s*scad-design\s*\n(?P<body>.*?)\n\s*-->",
    re.DOTALL,
)
FENCE_RE = re.compile(
    r"\s*```openscad\s*\n(?P<code>.*?)\n```",
    re.DOTALL,
)


@dataclass(frozen=True)
class DesignDocument:
    source_file: Path
    scope: str
    relative_path: Path
    external_name: str | None = None


@dataclass(frozen=True)
class DesignRender:
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
    vpr: list | None
    vpt: list | None
    vpd: float | None
    size: list[int] | None


def discover_design_documents(context: ProjectContext) -> list[DesignDocument]:
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
    candidates = sorted(design_file.parent.parent.glob("*.scad"))
    return candidates[0].resolve() if len(candidates) == 1 else None


def parse_design_document(
    document: DesignDocument,
) -> tuple[list[DesignRender], list[str]]:
    path = document.source_file
    text = path.read_text(encoding="utf-8")
    renders: list[DesignRender] = []
    errors: list[str] = []
    seen_images: set[str] = set()

    for idx, match in enumerate(BLOCK_RE.finditer(text), 1):
        try:
            data = yaml.safe_load(match.group("body")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path}: block {idx}: invalid YAML: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"{path}: block {idx}: declaration must be a YAML mapping")
            continue

        kind = data.get("type")
        image = data.get("image")

        if kind not in {"source-view", "inline"}:
            errors.append(f"{path}: block {idx}: unknown type {kind!r}")
            continue

        if not isinstance(image, str) or not image.endswith(".png"):
            errors.append(f"{path}: block {idx}: image must end in .png")
            continue

        if "/" in image or "\\" in image:
            errors.append(f"{path}: block {idx}: image must be a filename")
            continue

        if image in seen_images:
            errors.append(f"{path}: duplicate image {image}")
            continue
        seen_images.add(image)

        alt = data.get("alt")
        if not isinstance(alt, str) or not alt.strip():
            alt = Path(image).stem.replace("-", " ").replace("_", " ").strip().title()

        source = None
        module = None
        inline_code = None

        if kind == "source-view":
            module = data.get("module")
            if not isinstance(module, str) or not module.strip():
                errors.append(f"{path}: block {idx}: source-view requires module")
                continue

            source_value = data.get("source")
            if source_value:
                source = (path.parent.parent / str(source_value)).resolve()
            else:
                source = _infer_source(path)

            if source is None or not source.is_file():
                errors.append(
                    f"{path}: block {idx}: source could not be resolved; "
                    "specify source explicitly when multiple .scad files exist"
                )
                continue
        else:
            fence = FENCE_RE.match(text[match.end():])
            if not fence:
                errors.append(
                    f"{path}: block {idx}: inline render must be immediately "
                    "followed by an openscad fenced block"
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
                vpr=data.get("vpr"),
                vpt=data.get("vpt"),
                vpd=float(data["vpd"]) if data.get("vpd") is not None else None,
                size=data.get("size"),
            )
        )

    return renders, errors


def lint_design(context: ProjectContext):
    all_renders: list[DesignRender] = []
    errors: list[str] = []

    for document in discover_design_documents(context):
        renders, doc_errors = parse_design_document(document)
        all_renders.extend(renders)
        errors.extend(doc_errors)

    return all_renders, errors


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


def _entrypoint(render: DesignRender) -> str:
    lines: list[str] = []

    if render.kind == "source-view":
        assert render.source is not None
        lines.append(f"use <{render.source.as_posix()}>")

    lines.append("$fn = 120;")

    if render.vpr is not None:
        lines.append(f"$vpr = {_lit(render.vpr)};")
    if render.vpt is not None:
        lines.append(f"$vpt = {_lit(render.vpt)};")
    if render.vpd is not None:
        lines.append(f"$vpd = {_lit(render.vpd)};")

    if render.kind == "source-view":
        assert render.module is not None
        if render.view is None:
            lines.append(f"{render.module}();")
        else:
            lines.append(f"{render.module}(view = {_lit(render.view)});")
    else:
        lines.append(render.inline_code or "")

    return "\n".join(lines) + "\n"


def _materialized_document_path(context: ProjectContext, document: DesignDocument) -> Path:
    build_root = context.path(context.config["paths"]["build_root"])
    root = build_root / "design"

    if document.scope == "project":
        return root / "project" / document.relative_path

    assert document.external_name
    return root / "ext" / document.external_name / document.relative_path


def _materialize_markdown(
    source_text: str,
    renders: list[DesignRender],
) -> str:
    # Work backwards so source offsets remain valid.
    result = source_text

    for render in sorted(renders, key=lambda item: item.block_start, reverse=True):
        replacement = f"![{render.alt}](img/{render.image})"
        result = result[:render.block_start] + replacement + result[render.block_end:]

    return result


def build_design(context: ProjectContext) -> None:
    renders, errors = lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    documents = discover_design_documents(context)

    by_document: dict[Path, list[DesignRender]] = {
        document.source_file: [] for document in documents
    }
    for render in renders:
        by_document.setdefault(render.document.source_file, []).append(render)

    openscad = context.config.get("openscad", {}) or {}
    common_flags = [str(v) for v in openscad.get("common_flags", [])]
    render_flags = [str(v) for v in openscad.get("render_flags", ["--render"])]
    default_size = openscad.get("image_size", [1600, 1000])

    build_root = context.path(context.config["paths"]["build_root"])
    materialized_root = build_root / "design"

    # Build the entire documentation tree in a staging directory. Only replace
    # bld/design after all renders and Markdown generation succeed.
    with tempfile.TemporaryDirectory(prefix="scad-project-design-build-") as td:
        stage = Path(td) / "design"
        stage.mkdir(parents=True, exist_ok=True)

        entry_root = Path(td) / "entrypoints"
        entry_root.mkdir(parents=True, exist_ok=True)

        for document in documents:
            if document.scope == "project":
                out_doc = stage / "project" / document.relative_path
            else:
                assert document.external_name
                out_doc = stage / "ext" / document.external_name / document.relative_path

            out_doc.parent.mkdir(parents=True, exist_ok=True)
            image_dir = out_doc.parent / "img"
            image_dir.mkdir(parents=True, exist_ok=True)

            doc_renders = by_document.get(document.source_file, [])

            for index, render in enumerate(doc_renders, start=1):
                entry = entry_root / (
                    f"{document.scope}-{document.external_name or 'project'}-"
                    f"{len(list(entry_root.glob('*.scad'))) + 1:04d}.scad"
                )
                entry.write_text(_entrypoint(render), encoding="utf-8")

                size = render.size or default_size
                output = image_dir / render.image

                run_checked(
                    [
                        "xvfb-run",
                        "-a",
                        "openscad",
                        *common_flags,
                        *render_flags,
                        f"--imgsize={int(size[0])},{int(size[1])}",
                        "-o",
                        str(output),
                        str(entry),
                    ],
                    cwd=context.root,
                )

                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f"Missing or empty design render: {output}")

            source_text = document.source_file.read_text(encoding="utf-8")
            materialized = _materialize_markdown(source_text, doc_renders)
            out_doc.write_text(materialized, encoding="utf-8")

        # Generate a simple navigation index for the materialized tree.
        lines = [
            "# Design documentation",
            "",
            "This tree is generated from project and external `design.md` sources.",
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

    print(f"Materialized design documentation: {materialized_root.relative_to(context.root)}")
