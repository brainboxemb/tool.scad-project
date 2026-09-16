"""Validate SCAD tooling expectations for the running CLI/workflow."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from . import __version__
from .config import ProjectContext
from .repository import WORKFLOW_USE_RE


SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _tag(version: str) -> str:
    value = str(version).strip()
    return value if value.startswith("v") else f"v{value}"


def _tooling_entry(context: ProjectContext) -> dict | None:
    tooling = context.config.get("tooling", {}) or {}
    modern = tooling.get("tool_scad_project")
    return modern if isinstance(modern, dict) else None


def configured_tool_ref(context: ProjectContext) -> str | None:
    tooling = context.config.get("tooling", {}) or {}
    modern = tooling.get("tool_scad_project")
    if isinstance(modern, dict):
        value = modern.get("ref")
        return str(value).strip() if value else None

    legacy = tooling.get("tool_scad_project_version")
    return str(legacy).strip() if legacy else None


def _checked_out_tool_sha(context: ProjectContext) -> str | None:
    entry = _tooling_entry(context)
    path = str(entry.get("path", "tools/tool.scad-project")) if entry else "tools/tool.scad-project"
    root = context.path(path)
    if not root.exists():
        return None

    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        cwd=context.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if FULL_SHA_RE.fullmatch(value) else None


def _workflow_ref_errors(context: ProjectContext, expected_ref: str) -> list[str]:
    workflow_dir = context.root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []

    errors: list[str] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        for match in WORKFLOW_USE_RE.finditer(text):
            ref = match.group(2)
            if ref != expected_ref:
                errors.append(
                    "reusable workflow ref mismatch: "
                    f"{path.relative_to(context.root)} uses {ref}, "
                    f"project.yml expects {expected_ref}"
                )
    return errors


def tooling_errors(context: ProjectContext) -> list[str]:
    """Check configured tool policy, checked-out gitlink and workflow callers."""

    errors: list[str] = []
    expected = configured_tool_ref(context)
    if not expected:
        errors.append("Missing tooling tool.scad-project ref")
        return errors

    tool_sha = _checked_out_tool_sha(context)
    if FULL_SHA_RE.fullmatch(expected) and tool_sha and expected.lower() != tool_sha.lower():
        errors.append(
            "tool.scad-project gitlink mismatch: "
            f"project.yml expects {expected}, checked out {tool_sha}"
        )

    expected_workflow_ref = _tag(expected) if SEMVER_TAG_RE.fullmatch(expected) else expected
    errors.extend(_workflow_ref_errors(context, expected_workflow_ref))

    # Release tags provide the package/workflow-version invariant. The gitlink
    # remains the exact Git content pointer while consumer YAML stays readable.
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
