from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser
import shutil
import subprocess

from .config import ProjectContext
from .process import run_checked


@dataclass(frozen=True)
class External:
    name: str
    kind: str
    url: str
    path: str
    required_file: str | None = None

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
    errors = validate_externals_config(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    modules = _gitmodules(context)

    for external in configured_externals(context):
        path = external.path.replace("\\", "/").rstrip("/")

        if path not in modules:
            target = external.root(context)
            if target.exists() and any(target.iterdir()):
                raise RuntimeError(
                    f"Cannot add external {external.name}: path already contains "
                    f"files: {path}"
                )
            if target.exists():
                target.rmdir()

            run_checked(
                ["git", "submodule", "add", external.url, path],
                cwd=context.root,
            )
            modules = _gitmodules(context)

    # Use gitlinks already committed in the parent repository. This command
    # restores their pinned commits rather than silently following remote HEAD.
    run_checked(
        ["git", "submodule", "sync", "--recursive"],
        cwd=context.root,
    )
    run_checked(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=context.root,
    )


def sync_externals(context: ProjectContext) -> None:
    errors = validate_externals_config(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    run_checked(
        ["git", "submodule", "sync", "--recursive"],
        cwd=context.root,
    )
    run_checked(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=context.root,
    )


def deinit_externals(context: ProjectContext) -> None:
    """Deinitialize configured externals without deleting repository metadata.

    The parent repository keeps .gitmodules and the gitlink. A later
    externals-init/sync restores the exact pinned commit.
    """

    modules = _gitmodules(context)

    for external in configured_externals(context):
        path = external.path.replace("\\", "/").rstrip("/")
        if path not in modules:
            print(f"Skipping unregistered external: {external.name}")
            continue

        run_checked(
            ["git", "submodule", "deinit", "-f", "--", path],
            cwd=context.root,
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
