"""Project policy for selecting generated design documentation.

The render engine in :mod:`scad_project.design` remains responsible for
rendering and discovery. This module applies consumer-level policy without
changing configured external source dependencies.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from . import design as _design
from .config import ProjectContext


def include_external_designs(context: ProjectContext) -> bool:
    """Return whether configured external design documentation is included."""

    config = context.config.get("design", {}) or {}
    if not isinstance(config, dict):
        raise RuntimeError("project.yml: design must be a mapping")

    value = config.get("include_externals", True)
    if not isinstance(value, bool):
        raise RuntimeError(
            "project.yml: design.include_externals must be true or false"
        )
    return value


@contextmanager
def _design_discovery_policy(context: ProjectContext) -> Iterator[None]:
    """Temporarily restrict design discovery to project-owned documents."""

    if include_external_designs(context):
        yield
        return

    original = _design.discover_design_documents

    def project_only(ctx: ProjectContext):
        return [document for document in original(ctx) if document.scope == "project"]

    _design.discover_design_documents = project_only
    try:
        yield
    finally:
        _design.discover_design_documents = original


def lint_design(context: ProjectContext):
    """Lint only the design documentation selected by project policy."""

    with _design_discovery_policy(context):
        return _design.lint_design(context)


def build_design(context: ProjectContext) -> None:
    """Build design documentation while honoring ``include_externals``."""

    include_externals = include_external_designs(context)
    with _design_discovery_policy(context):
        _design.build_design(context)

    if include_externals:
        return

    build_root = context.path(context.config["paths"]["build_root"])
    index = build_root / "design" / "README.md"
    if not index.is_file():
        return

    text = index.read_text(encoding="utf-8")
    text = text.replace(
        "- No external design documents found.",
        "- External design documentation intentionally omitted by "
        "`design.include_externals: false`.",
    )
    index.write_text(text, encoding="utf-8")
