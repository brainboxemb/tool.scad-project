"""Bridge generic repository operations to tool.git-project.

Generic Git/submodule behaviour is deliberately not implemented here.  This
module only invokes the pinned generic tool and performs SCAD-specific workflow
alignment after a dependency change.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from .config import ProjectContext
from .process import run_checked


GIT_TOOL_PATH = "tools/tool.git-project"
SCAD_TOOL_PATH = "tools/tool.scad-project"
WORKFLOW_USE_RE = re.compile(
    r"(brainboxemb/tool\.scad-project/\.github/workflows/"
    r"(?:project-build|project-verify|project-production|project-release)\.yml)@([^\s\"']+)"
)


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


def _checked_out_scad_tool_sha(context: ProjectContext) -> str:
    tool_root = context.path(SCAD_TOOL_PATH)
    result = subprocess.run(
        ["git", "-C", str(tool_root), "rev-parse", "HEAD"],
        cwd=context.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            "Cannot resolve checked-out tool.scad-project commit: " + detail
        )
    return result.stdout.strip()


def sync_workflow_refs(context: ProjectContext) -> list[Path]:
    """Pin SCAD reusable-workflow callers to the checked-out tool commit.

    Git dependency movement belongs to tool.git-project.  Workflow caller
    alignment is SCAD-specific because GitHub reusable workflows are part of the
    public tool.scad-project contract and must use the exact checked-out commit.
    """

    workflow_dir = context.root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []

    tool_sha = _checked_out_scad_tool_sha(context)
    changed: list[Path] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        updated = WORKFLOW_USE_RE.sub(
            lambda match: f"{match.group(1)}@{tool_sha}",
            text,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)

    for path in changed:
        print(f"Updated SCAD workflow ref: {path.relative_to(context.root)}")
    if not changed:
        print(f"SCAD workflow refs already aligned to {tool_sha[:12]}")
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