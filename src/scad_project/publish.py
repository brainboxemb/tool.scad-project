"""Publish generated output as mutable orphan branch snapshots."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

from .config import ProjectContext
from .process import run_checked


def _publish_snapshot(source_root: Path, branch: str, commit_message: str) -> None:
    """Force-replace one generated branch with ``source_root`` contents."""

    if not source_root.exists() or not any(source_root.iterdir()):
        raise RuntimeError(f"Generated output directory is empty: {source_root}")

    repository = os.environ.get("GITHUB_REPOSITORY")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    if not repository:
        raise RuntimeError(
            "GITHUB_REPOSITORY is required for publication. "
            "Use this command from CI or provide an authenticated Git remote workflow."
        )

    with tempfile.TemporaryDirectory(prefix="scad-project-publish-") as td:
        snapshot = Path(td)
        for item in source_root.iterdir():
            dest = snapshot / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        run_checked(["git", "init", "-q"], cwd=snapshot)
        run_checked(["git", "checkout", "--orphan", "snapshot"], cwd=snapshot)
        run_checked(["git", "config", "user.name", "github-actions[bot]"], cwd=snapshot)
        run_checked(
            [
                "git", "config", "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            cwd=snapshot,
        )
        run_checked(["git", "add", "."], cwd=snapshot)
        run_checked(["git", "commit", "-q", "-m", commit_message], cwd=snapshot)
        run_checked(
            ["git", "remote", "add", "origin", f"{server}/{repository}.git"],
            cwd=snapshot,
        )
        run_checked(
            ["git", "push", "--force", "origin", f"HEAD:{branch}"],
            cwd=snapshot,
        )


def publish_build(context: ProjectContext) -> None:
    """Publish the configured build root to the mutable build branch."""

    build_root = context.path(context.config["paths"]["build_root"])
    publication = context.config.get("publication", {}) or {}
    branch = publication.get("build_branch", "build")
    _publish_snapshot(build_root, branch, "Generated build snapshot")
    print(f"Published generated build to branch: {branch}")


def publish_verification(context: ProjectContext) -> None:
    """Publish configured verification evidence to its generated branch."""

    verification = context.config.get("verification", {}) or {}
    output_root = verification.get("output_root")
    if not output_root:
        raise RuntimeError("verification.output_root is required for publish-verification")

    publication = context.config.get("publication", {}) or {}
    branch = publication.get("verification_branch", "verification")
    _publish_snapshot(
        context.path(output_root),
        branch,
        "Generated verification snapshot",
    )
    print(f"Published verification output to branch: {branch}")
