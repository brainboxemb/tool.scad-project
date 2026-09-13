"""Stable SCAD producer actions for cacheable repository orchestration.

These actions compose existing SCAD domain operations into complete producer results.
They intentionally do not own Moon/GitHub cache restore, materialization evidence, or
publication side effects.
"""

from __future__ import annotations

from .build_engine import build_project
from .config import ProjectContext
from .design_policy import build_design, lint_design
from .docs import lint_docs
from .externals import check_externals, validate_externals_config
from .index import write_build_index
from .publish import write_publication_info
from .tooling import tooling_errors
from .verification import run_functional_verification


def _producer_validation_errors(context: ProjectContext) -> list[str]:
    """Return SCAD-domain validation errors shared by producer actions."""

    errors = (
        tooling_errors(context)
        + validate_externals_config(context)
        + check_externals(context)
        + lint_docs(context)
    )
    _, design_errors = lint_design(context)
    errors.extend(design_errors)
    return errors


def _require_valid_producer_context(context: ProjectContext) -> None:
    errors = _producer_validation_errors(context)
    if errors:
        raise RuntimeError("\n".join(errors))


def produce_build(context: ProjectContext) -> None:
    """Produce the complete normal SCAD build result.

    The result includes generated design documentation, configured build targets,
    generated build indexes/galleries, and producer provenance. Target execution
    and fine-grained reuse remain owned by the configured build engine/SCons.
    """

    _require_valid_producer_context(context)
    build_design(context)
    build_project(context)
    write_build_index(context)
    write_publication_info(context, "build")


def produce_verification(context: ProjectContext) -> None:
    """Produce the complete SCAD verification result without running normal Build."""

    _require_valid_producer_context(context)
    run_functional_verification(context)
    write_publication_info(context, "verification")
