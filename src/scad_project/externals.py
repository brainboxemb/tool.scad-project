"""Interpret and verify SCAD external dependencies.

Generic registration, initialization, ref resolution and update are owned by
`tool.git-project`.  This module keeps only the SCAD-facing view needed for
build/search-path checks and compatibility status output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser
import subprocess

from .config import ProjectContext


@dataclass(frozen=True)
class External:
    name: str
    kind: str
    url: str
    path: str
    required_file: str | None = None
    ref: str | None = None

    def root(self, context: ProjectContext) -> Path:
        return context.path(self.path)


def configured_externals(context: ProjectContext) -> list[External]:
    raw = context.config.get("externals")

    # v0.1 compatibility: accept the old `libraries` block while projects
    # migrate to the clearer `externals` schema.
    if raw is None:
        raw = context.config.get("libraries", [])

    result: list[External] = []
    for item in raw or []:
        result.append(
            External(
                name=item["name"],
                kind=item.get("type", "git-submodule"),
                url=item.get("url", ""),
                path=item["path"],
                required_file=item.get("required_file"),
                ref=item.get("ref"),
            )
        )
    return result


def _gitmodules(context: ProjectContext) -> dict[str, dict[str, str]]:
    path = context.root / ".gitmodules"
    if not path.is_file():
        return {}

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    result: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        if not section.startswith("submodule "):
            continue
        module_path = parser.get(section, "path", fallback="")
        if module_path:
            result[module_path.replace("\\", "/")] = {
                "url": parser.get(section, "url", fallback=""),
                "section": section,
            }
    return result


def validate_externals_config(context: ProjectContext) -> list[str]:
    errors: list[str] = []
    seen_paths: set[str] = set()
    seen_names: set[str] = set()

    for external in configured_externals(context):
        if external.kind != "git-submodule":
            errors.append(
                f"External {external.name}: unsupported type {external.kind!r}"
            )
        if not external.url:
            errors.append(f"External {external.name}: url is required")
        if external.name in seen_names:
            errors.append(f"Duplicate external name: {external.name}")
        seen_names.add(external.name)

        normalized = external.path.replace("\\", "/").rstrip("/")
        if normalized in seen_paths:
            errors.append(f"Duplicate external path: {normalized}")
        seen_paths.add(normalized)

        if Path(normalized).is_absolute() or normalized.startswith("../"):
            errors.append(
                f"External {external.name}: path must stay inside project: "
                f"{external.path}"
            )

    return errors


def external_status(context: ProjectContext) -> list[dict[str, str]]:
    """Return SCAD-oriented status without changing generic dependencies."""

    modules = _gitmodules(context)
    rows: list[dict[str, str]] = []

    for external in configured_externals(context):
        normalized = external.path.replace("\\", "/").rstrip("/")
        root = external.root(context)
        registered = normalized in modules
        initialized = (root / ".git").exists()

        if initialized:
            proc = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                cwd=context.root,
                text=True,
                capture_output=True,
            )
            commit = proc.stdout.strip() if proc.returncode == 0 else "unknown"
        else:
            commit = "-"

        if initialized:
            state = "initialized"
        elif registered:
            state = "registered"
        else:
            state = "missing"

        rows.append(
            {
                "name": external.name,
                "path": normalized,
                "state": state,
                "commit": commit,
            }
        )

    return rows


def init_externals(context: ProjectContext) -> None:
    """Compatibility alias for generic dependency bootstrap."""

    from .repository import repo_sync

    repo_sync(context)


def sync_externals(context: ProjectContext) -> None:
    """Compatibility alias for generic dependency bootstrap."""

    from .repository import repo_sync

    repo_sync(context)


def deinit_externals(context: ProjectContext) -> None:
    """Reject generic Git mutation that no longer belongs to the SCAD layer."""

    raise RuntimeError(
        "externals-deinit is no longer a tool.scad-project-owned operation; "
        "managed Git dependencies are owned by tool.git-project"
    )


def check_externals(context: ProjectContext) -> list[str]:
    errors: list[str] = []

    for external in configured_externals(context):
        root = external.root(context)
        if not (root / ".git").exists():
            errors.append(
                f"External not initialized: {external.name} ({external.path})"
            )
            continue

        if external.required_file:
            required = root / external.required_file
            if not required.is_file():
                errors.append(
                    f"External {external.name} is missing required file: "
                    f"{external.required_file}"
                )

    return errors
