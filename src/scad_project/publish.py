"""Publish generated build output as a mutable orphan branch snapshot."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

from .config import ProjectContext
from .process import run_checked


def publish_build(context: ProjectContext) -> None:
    """Force-replace the configured build branch with the current bld snapshot."""

    build_root = context.path(context.config["paths"]["build_root"])
    if not build_root.exists() or not any(build_root.iterdir()):
        raise RuntimeError("Build directory is empty; run build/design-build first.")

    publication = context.config.get("publication", {}) or {}
    branch = publication.get("build_branch", "build")

    repository = os.environ.get("GITHUB_REPOSITORY")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

    if not repository:
        raise RuntimeError(
            "GITHUB_REPOSITORY is required for publish-build. "
            "Use this command from CI or provide an authenticated Git remote workflow."
        )

    with tempfile.TemporaryDirectory(prefix="scad-project-build-publish-") as td:
        snapshot = Path(td)

        # Publish the content of bld as the branch root, not the source tree.
        for item in build_root.iterdir():
            dest = snapshot / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # A fresh repository makes the generated branch independent of source history.
        run_checked(["git", "init", "-q"], cwd=snapshot)
        run_checked(["git", "checkout", "--orphan", "snapshot"], cwd=snapshot)
        run_checked(["git", "config", "user.name", "github-actions[bot]"], cwd=snapshot)
        run_checked(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            cwd=snapshot,
        )
        run_checked(["git", "add", "."], cwd=snapshot)
        run_checked(
            ["git", "commit", "-q", "-m", "Generated build snapshot"],
            cwd=snapshot,
        )
        run_checked(
            ["git", "remote", "add", "origin", f"{server}/{repository}.git"],
            cwd=snapshot,
        )
        run_checked(
            ["git", "push", "--force", "origin", f"HEAD:{branch}"],
            cwd=snapshot,
        )

    print(f"Published generated build to branch: {branch}")
