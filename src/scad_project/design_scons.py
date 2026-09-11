"""Selective SCons backend for generated design documentation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from . import design as _design
from .build import _raw_png_path, _require_output, _watermark_text
from .build_engine import (
    SCONS_CACHE_ROOT,
    SCONS_STATE_ROOT,
    _relative_or_absolute,
    _search_paths,
)
from .config import ProjectContext
from .externals import configured_externals
from .openscad_deps import scan_openscad_dependencies
from .process import run_checked


DESIGN_STAGE_ROOT = ".cache/scad-project/design-stage"


def _backend_signature() -> str:
    """Return a signature for code/tooling that changes design render output."""

    digest = hashlib.sha256()
    package_root = Path(__file__).resolve().parent
    for name in (
        "design_scons.py",
        "design_scons_driver.py",
        "design.py",
        "openscad_deps.py",
        "process.py",
    ):
        path = package_root / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())

    digest.update(os.environ.get("SCAD_TOOLCHAIN_IMAGE", "").encode("utf-8"))
    digest.update(os.environ.get("SCAD_TOOLCHAIN_VERSION", "").encode("utf-8"))
    return digest.hexdigest()


def _document_output(stage: Path, document: _design.DesignDocument) -> Path:
    if document.scope == "project":
        return stage / "project" / document.relative_path

    assert document.external_name
    return stage / "ext" / document.external_name / document.relative_path


def _python_dependencies(context: ProjectContext) -> list[Path]:
    """Return a conservative Python source set for PythonSCAD design renders."""

    roots = [path.resolve() for path in _design._project_design_roots(context)]
    roots.extend(external.root(context).resolve() for external in configured_externals(context))

    dependencies: set[Path] = set()
    for root in roots:
        if root.exists():
            dependencies.update(path.resolve() for path in root.rglob("*.py"))
    return sorted(dependencies)


def _render_dependencies(
    context: ProjectContext,
    render: _design.DesignRender,
    entry: Path | None,
    *,
    search_paths: list[Path],
    python_dependencies: list[Path],
) -> list[str]:
    dependencies: set[Path] = {render.document.source_file.resolve()}

    if render.source is not None:
        dependencies.add(render.source.resolve())
    if entry is not None:
        dependencies.add(entry.resolve())

    if render.engine == "openscad":
        scan_root = entry or render.source
        if scan_root is not None:
            dependencies.update(
                scan_openscad_dependencies(
                    scan_root,
                    search_paths=search_paths,
                )
            )
    elif render.engine == "pythonscad":
        # PythonSCAD import scanning is not available yet. Depending on the
        # configured project/external Python trees is conservative but safe.
        dependencies.update(python_dependencies)

    return [
        _relative_or_absolute(context.root, path)
        for path in sorted(dependencies)
    ]


def _write_manifest(
    context: ProjectContext,
    targets: list[dict[str, Any]],
) -> Path:
    state_root = context.path(SCONS_STATE_ROOT)
    state_root.mkdir(parents=True, exist_ok=True)
    manifest = state_root / "design-manifest.json"

    payload = {
        "project_root": str(context.root.resolve()),
        "cache_root": str(context.path(SCONS_CACHE_ROOT)),
        "sconsign": str(state_root / ".design.sconsign.dblite"),
        "execution_log": str(state_root / "executed-design-targets.txt"),
        "targets": targets,
    }
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_report(context: ProjectContext, manifest: Path) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    execution_log = Path(payload["execution_log"])
    executed = (
        execution_log.read_text(encoding="utf-8").splitlines()
        if execution_log.is_file()
        else []
    )
    outputs = [spec["output"] for spec in payload["targets"]]
    executed_set = set(executed)
    not_executed = [output for output in outputs if output not in executed_set]

    report = {
        "engine": "scons",
        "target_count": len(outputs),
        "executed_count": len(executed),
        "not_executed_count": len(not_executed),
        "executed": executed,
        "not_executed": not_executed,
    }
    report_path = context.path(SCONS_STATE_ROOT) / "last-design-build.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "SCons design summary: "
        f"targets={len(outputs)} executed={len(executed)} "
        f"not-executed={len(not_executed)}"
    )
    for output in executed:
        print(f"  built: {output}")
    for output in not_executed:
        print(f"  cache/current: {output}")


def _write_index(stage: Path, documents: list[_design.DesignDocument]) -> None:
    lines = [
        "# Design documentation",
        "",
        "Generated from source `design.md` files.",
        "",
        "## Project",
        "",
    ]

    project_docs = [document for document in documents if document.scope == "project"]
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
    external_docs = [document for document in documents if document.scope == "external"]
    if external_docs:
        for document in external_docs:
            assert document.external_name
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


def build_design(context: ProjectContext) -> None:
    """Generate design docs with one SCons target per generated PNG."""

    renders, errors = _design.lint_design(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    documents = _design.discover_design_documents(context)
    by_document: dict[Path, list[_design.DesignRender]] = {
        document.source_file: [] for document in documents
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
    stage = context.path(DESIGN_STAGE_ROOT)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    state_root = context.path(SCONS_STATE_ROOT)
    entry_root = state_root / "design-entrypoints"
    if entry_root.exists():
        shutil.rmtree(entry_root)
    entry_root.mkdir(parents=True, exist_ok=True)

    search_paths = [Path(value).resolve() for value in _search_paths(context)]
    python_dependencies = _python_dependencies(context)
    backend_signature = _backend_signature()
    warnings: list[str] = []
    targets: list[dict[str, Any]] = []

    for document in documents:
        out_doc = _document_output(stage, document)
        out_doc.parent.mkdir(parents=True, exist_ok=True)
        _design._copy_source_assets(document, out_doc)
        image_dir = out_doc.parent / "img"
        image_dir.mkdir(parents=True, exist_ok=True)

        doc_renders = by_document.get(document.source_file, [])
        for render in doc_renders:
            output = image_dir / render.image
            render_output = _raw_png_path(output) if watermark_text else output
            output.unlink(missing_ok=True)
            if render_output != output:
                render_output.unlink(missing_ok=True)

            entry: Path | None = None
            if render.engine == "openscad":
                identity = (
                    f"{document.scope}:{document.external_name or ''}:"
                    f"{document.relative_path.as_posix()}:{render.image}"
                )
                entry_name = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
                entry = entry_root / f"{entry_name}.scad"
                entry.write_text(
                    _design._openscad_entrypoint(render),
                    encoding="utf-8",
                )

            size = render.size or default_size
            command = _design._render_args(
                context,
                render,
                entry,
                render_output,
                size,
            )
            cwd = (
                render.source.parent
                if render.engine == "pythonscad" and render.source is not None
                else context.root
            )
            targets.append(
                {
                    "output": _relative_or_absolute(context.root, output),
                    "render_output": _relative_or_absolute(context.root, render_output),
                    "watermark_text": watermark_text,
                    "command": [str(value) for value in command],
                    "cwd": _relative_or_absolute(context.root, cwd),
                    "dependencies": _render_dependencies(
                        context,
                        render,
                        entry,
                        search_paths=search_paths,
                        python_dependencies=python_dependencies,
                    ),
                    "backend_signature": backend_signature,
                }
            )

        source_text = document.source_file.read_text(encoding="utf-8")
        generated = _design._generate_markdown(source_text, doc_renders)
        out_doc.write_text(generated, encoding="utf-8")

    _write_index(stage, documents)

    manifest = _write_manifest(context, targets)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    execution_log = Path(payload["execution_log"])
    execution_log.unlink(missing_ok=True)

    if targets:
        if shutil.which("scons") is None:
            raise RuntimeError(
                "SCons design build requested but 'scons' is not installed"
            )

        driver = Path(__file__).with_name("design_scons_driver.py").resolve()
        print(
            f"SCons design engine: {len(targets)} target(s), "
            f"cache={context.path(SCONS_CACHE_ROOT)}"
        )
        run_checked(
            [
                "scons",
                "-Q",
                "-f",
                str(driver),
                f"SCAD_PROJECT_MANIFEST={manifest}",
            ],
            cwd=context.root,
        )

    _write_report(context, manifest)

    for document in documents:
        out_doc = _document_output(stage, document)
        source_text = out_doc.read_text(encoding="utf-8")
        missing = _design._missing_local_images(source_text, out_doc)
        if missing:
            relative = ", ".join(str(path.relative_to(stage)) for path in missing)
            message = (
                f"{document.source_file}: missing generated image(s): "
                f"{relative}"
            )
            if document.scope == "project":
                raise RuntimeError(message)
            warnings.append(message)

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
