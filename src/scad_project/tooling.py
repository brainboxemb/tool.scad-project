"""Validate project tooling expectations for the running CLI/workflow."""

from __future__ import annotations

import os
import re

from . import __version__
from .config import ProjectContext


SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _tag(version: str) -> str:
    value = str(version).strip()
    return value if value.startswith("v") else f"v{value}"


def configured_tool_ref(context: ProjectContext) -> str | None:
    tooling = context.config.get("tooling", {}) or {}
    modern = tooling.get("tool_scad_project")
    if isinstance(modern, dict):
        value = modern.get("ref")
        return str(value).strip() if value else None

    legacy = tooling.get("tool_scad_project_version")
    return str(legacy).strip() if legacy else None


def tooling_errors(context: ProjectContext) -> list[str]:
    """Check what can be proven from the running tool.

    Exact semantic-version tags must match the package version. Floating
    policies (``latest`` or a branch such as ``main``) are resolved by
    ``repo-update`` and locked by the parent gitlink, so a package-version
    equality check would be misleading for unreleased branch commits.
    """

    errors: list[str] = []
    expected = configured_tool_ref(context)
    if not expected:
        errors.append("Missing tooling tool.scad-project ref")
        return errors

    if SEMVER_TAG_RE.fullmatch(expected):
        expected_tag = _tag(expected)
        running_tag = _tag(__version__)
        if expected_tag != running_tag:
            errors.append(
                "tool.scad-project version mismatch: "
                f"project.yml expects {expected_tag}, running CLI is {running_tag}"
            )

        workflow = os.environ.get("SCAD_PROJECT_WORKFLOW_VERSION")
        if workflow and SEMVER_TAG_RE.fullmatch(workflow):
            if _tag(workflow) != expected_tag:
                errors.append(
                    "reusable workflow version mismatch: "
                    f"project.yml expects {expected_tag}, workflow is {_tag(workflow)}"
                )

    return errors
