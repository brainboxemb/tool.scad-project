"""Generate GitHub Release notes from the project's changelog."""

from __future__ import annotations

import os
from pathlib import Path
import re

from .config import ProjectContext
from .release import release_branches


_VERSION_HEADING_RE = re.compile(
    r"^##\s+(?:\[(?P<bracket>[^\]]+)\]|(?P<plain>\S+))(?:\s+-\s+.*)?\s*$"
)
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _normalized_version(value: str) -> str:
    value = value.strip()
    return value[1:] if value.startswith("v") else value


def changelog_release_section(context: ProjectContext, version: str) -> str:
    """Return the Markdown body for one exact version heading."""

    publication = context.config.get("publication", {}) or {}
    release = publication.get("release", {}) or {}
    changelog_value = release.get("changelog", "CHANGELOG.md")
    changelog = context.path(str(changelog_value))
    if not changelog.is_file():
        raise RuntimeError(f"Release changelog does not exist: {changelog}")

    wanted = _normalized_version(version)
    lines = changelog.read_text(encoding="utf-8").splitlines()
    start: int | None = None

    for index, line in enumerate(lines):
        match = _VERSION_HEADING_RE.match(line)
        if not match:
            continue
        token = match.group("bracket") or match.group("plain") or ""
        if _normalized_version(token) == wanted:
            start = index + 1
            break

    if start is None:
        raise RuntimeError(
            f"CHANGELOG.md has no release section for {version}; "
            "add the release notes before publishing"
        )

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise RuntimeError(f"CHANGELOG.md release section for {version} is empty")
    return body


def release_notes_text(
    context: ProjectContext,
    version: str,
    source_sha: str,
    repository: str | None = None,
    server_url: str | None = None,
) -> str:
    """Build release notes from changelog content plus stable browse links."""

    if not _SHA_RE.fullmatch(source_sha):
        raise RuntimeError("release source SHA must be an exact 40-character commit SHA")

    branches = release_branches(context, version)
    changelog_body = changelog_release_section(context, version)
    repository = repository or os.environ.get("GITHUB_REPOSITORY", "")
    server = (server_url or os.environ.get("GITHUB_SERVER_URL", "https://github.com")).rstrip("/")
    if not repository:
        raise RuntimeError("repository is required to generate release browse links")

    return (
        f"{changelog_body}\n\n"
        "## Release outputs\n\n"
        f"Source commit: `{source_sha}`\n\n"
        "Browse the immutable generated release output directly on GitHub:\n\n"
        f"- [Build and design documentation]({server}/{repository}/tree/{branches.build_branch})\n"
        f"- [Verification evidence]({server}/{repository}/tree/{branches.verification_branch})\n\n"
        "Downloadable build, verification and STL bundles are attached to this release "
        "together with `SHA256SUMS.txt`.\n"
    )


def write_release_notes(
    context: ProjectContext,
    version: str,
    source_sha: str,
    output: Path,
    repository: str | None = None,
) -> Path:
    """Write release notes to an explicit output file."""

    resolved = output if output.is_absolute() else context.root / output
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        release_notes_text(context, version, source_sha, repository=repository),
        encoding="utf-8",
    )
    return resolved
