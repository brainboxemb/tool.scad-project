"""Validate that project config, local tooling and reusable workflow agree."""

from __future__ import annotations

import os

from . import __version__
from .config import ProjectContext


def _tag(version: str) -> str:
    """Normalize package version or tag to the canonical ``vX.Y.Z`` form."""

    value = str(version).strip()
    return value if value.startswith("v") else f"v{value}"


def tooling_errors(context: ProjectContext) -> list[str]:
    """Return version-alignment errors for the pinned project tooling.

    ``project.yml`` declares the expected tag. The running CLI represents the
    checked-out tool submodule. Reusable workflows additionally expose their
    own version through ``SCAD_PROJECT_WORKFLOW_VERSION``.
    """

    errors: list[str] = []
    tooling = context.config.get("tooling", {}) or {}
    expected = tooling.get("tool_scad_project_version")

    if not expected:
        errors.append("Missing value: tooling.tool_scad_project_version")
        return errors

    expected_tag = _tag(str(expected))
    running_tag = _tag(__version__)
    if expected_tag != running_tag:
        errors.append(
            "tool.scad-project version mismatch: "
            f"project.yml expects {expected_tag}, running CLI is {running_tag}"
        )

    workflow = os.environ.get("SCAD_PROJECT_WORKFLOW_VERSION")
    if workflow and _tag(workflow) != expected_tag:
        errors.append(
            "reusable workflow version mismatch: "
            f"project.yml expects {expected_tag}, workflow is {_tag(workflow)}"
        )

    return errors
