"""Stable SCAD producer actions for cacheable repository orchestration.

These actions compose existing SCAD domain operations into complete producer results.
They intentionally do not own Moon/GitHub cache restore, materialization evidence, or
publication side effects.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from . import __version__
from .build_engine import build_project
from .config import ProjectContext
from .design_policy import build_design, lint_design
from .docs import lint_docs
from .externals import check_externals, validate_externals_config
from .index import write_build_index
from .publish import write_publication_info
from .tooling import tooling_errors
from .verification import run_functional_verification


def _git_head(path: Path) -> str | None:
    """Return the exact checked-out commit for one Git worktree when available."""

    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value if len(value) == 40 else None


def _ensure_producer_provenance(context: ProjectContext) -> None:
    """Populate producer-owned revision context without overriding explicit CI input."""

    source_sha = _git_head(context.root)
    if source_sha:
        os.environ.setdefault("SCAD_PROJECT_SOURCE_SHA", source_sha)

    tooling = context.config.get("tooling", {}) or {}
    tool = tooling.get("tool_scad_project")
    tool_path = (
        str(tool.get("path", "tools/tool.scad-project"))
        if isinstance(tool, dict)
        else "tools/tool.scad-project"
    )
    tool_sha = _git_head(context.path(tool_path))
    if tool_sha:
        os.environ.setdefault("SCAD_PROJECT_TOOL_SHA", tool_sha)

    os.environ.setdefault("SCAD_PROJECT_WORKFLOW_VERSION", f"v{__version__}")


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

    _ensure_producer_provenance(context)
    _require_valid_producer_context(context)
    build_design(context)
    build_project(context)
    write_build_index(context)
    write_publication_info(context, "build")


def produce_verification(context: ProjectContext) -> None:
    """Produce the complete SCAD verification result without running normal Build."""

    _ensure_producer_provenance(context)
    _require_valid_producer_context(context)
    run_functional_verification(context)
    write_publication_info(context, "verification")
