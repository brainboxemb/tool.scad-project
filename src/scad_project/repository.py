"""Bridge generic repository operations to tool.git-project.

Generic Git/submodule behaviour is deliberately not implemented here. This
module only invokes the pinned generic tool and performs SCAD-specific workflow
alignment after a dependency change.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

from .config import ProjectContext
from .process import run_checked


GIT_TOOL_PATH = "tools/tool.git-project"
WORKFLOW_USE_RE = re.compile(
    r"(brainboxemb/tool\.scad-project/\.github/workflows/"
    r"(?:project-build|project-verify|project-production|project-release)\.yml)@([^\s\"']+)"
)
SEMVER_TOOL_REF_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def _generic_tool_argv(context: ProjectContext, command: str) -> list[str]:
    root = context.root.resolve()
    tool_root = root / GIT_TOOL_PATH

    if os.name == "nt":
        script = tool_root / "git-project.ps1"
        if not script.is_file():
            raise RuntimeError(
                "tool.git-project is not initialized; run the root bootstrap.ps1 first"
            )
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            command,
            "-RepoRoot",
            str(root),
        ]

    script = tool_root / "git-project.sh"
    if not script.is_file():
        raise RuntimeError(
            "tool.git-project is not initialized; run the root bootstrap.sh first"
        )
    return ["bash", str(script), command, "--repo", str(root)]


def run_generic_repository_command(context: ProjectContext, command: str) -> None:
    """Run one generic repository operation through the pinned Git tool."""

    if command not in {"validate", "bootstrap", "status", "update"}:
        raise RuntimeError(f"Unsupported generic repository command: {command}")
    run_checked(_generic_tool_argv(context, command), cwd=context.root)


def configured_scad_tool_ref(context: ProjectContext) -> str:
    """Return the released semantic tool ref exposed by project configuration."""

    tooling = context.config.get("tooling", {}) or {}
    tool = tooling.get("tool_scad_project")
    value = tool.get("ref") if isinstance(tool, dict) else None
    ref = str(value).strip() if value else ""
    if not ref:
        raise RuntimeError("Missing tooling tool.scad-project ref")
    if not SEMVER_TOOL_REF_RE.fullmatch(ref):
        raise RuntimeError(
            "tool.scad-project workflow callers require a released semantic ref "
            f"(vX.Y.Z), got {ref!r}"
        )
    return ref


def sync_workflow_refs(context: ProjectContext) -> list[Path]:
    """Align SCAD reusable-workflow callers to the configured semantic release.

    The submodule gitlink remains Git's exact immutable content pointer. Consumer
    workflow YAML stays human-readable and follows the released semantic ref from
    project.yml. The tool's validation layer separately checks that the running
    package/workflow version agrees with that configured release.
    """

    workflow_dir = context.root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []

    tool_ref = configured_scad_tool_ref(context)
    changed: list[Path] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        updated = WORKFLOW_USE_RE.sub(
            lambda match: f"{match.group(1)}@{tool_ref}",
            text,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)

    for path in changed:
        print(f"Updated SCAD workflow ref: {path.relative_to(context.root)} -> {tool_ref}")
    if not changed:
        print(f"SCAD workflow refs already aligned to {tool_ref}")
    return changed


def repository_validate(context: ProjectContext) -> None:
    """Validate generic project.yml when this is a split-config consumer."""

    if context.repository_config is not None:
        run_generic_repository_command(context, "validate")


def repo_sync(context: ProjectContext) -> None:
    """Compatibility command: generic bootstrap plus SCAD workflow alignment."""

    run_generic_repository_command(context, "bootstrap")
    sync_workflow_refs(context)


def repo_update(context: ProjectContext) -> None:
    """Generic dependency update followed by SCAD-specific workflow alignment."""

    run_generic_repository_command(context, "update")
    sync_workflow_refs(context)


def repo_status(context: ProjectContext) -> None:
    """Show generic dependency status through tool.git-project."""

    run_generic_repository_command(context, "status")
