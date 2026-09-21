"""Exact owner-local provenance for external sources used by SCons build targets."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

import yaml

from .config import ProjectContext
from .execution_evidence import resolve_source_revision


SCHEMA_NAME = "brainboxemb.scad-build-dependency-provenance"
SCHEMA_VERSION = 1


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _normalize_repository_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized[len("git@github.com:"):]
    return normalized


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _initialized_repository(path: Path) -> bool:
    if not path.is_dir():
        return False
    top = _git(path, "rev-parse", "--show-toplevel", check=False)
    if not top:
        return False
    return Path(top).resolve() == path.resolve()


def _external_dependencies(owner: Path) -> list[dict[str, str]]:
    """Read only owner-declared external metadata needed for provenance.

    Generic dependency initialization, ref resolution, update and dirty-state
    protection remain owned by tool.git-project. This reader never moves a
    dependency or interprets non-external dependency roles.
    """

    project = owner / "project.yml"
    if not project.is_file():
        return []

    try:
        payload = yaml.safe_load(project.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid dependency metadata in {project}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{project}: project.yml must contain a mapping")

    raw_dependencies = payload.get("dependencies", []) or []
    if not isinstance(raw_dependencies, list):
        raise RuntimeError(f"{project}: dependencies must be a list")

    result: list[dict[str, str]] = []
    for raw in raw_dependencies:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("role", "")).strip() != "external":
            continue
        if str(raw.get("type", "")).strip() != "git-submodule":
            continue

        required = ("name", "url", "path", "ref")
        values = {key: str(raw.get(key, "")).strip() for key in required}
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                f"{project}: external dependency is missing {', '.join(missing)}"
            )

        dependency_path = (owner / values["path"]).resolve()
        try:
            dependency_path.relative_to(owner.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"{project}: external dependency path escapes its owner: "
                f"{values['path']}"
            ) from exc

        result.append(values)
    return result


def _collect_dependency_nodes(
    root: Path,
    owner: Path,
    *,
    lineage: tuple[str, ...],
    depth: int,
    nodes: list[dict[str, Any]],
) -> None:
    for dependency in _external_dependencies(owner):
        repository = _normalize_repository_url(dependency["url"])
        if repository in lineage:
            raise RuntimeError(
                f"Dependency cycle while collecting SCAD provenance: "
                f"{dependency['url']}"
            )

        worktree = (owner / dependency["path"]).resolve()
        # The generic bootstrap owns initialization. An uninitialized external
        # cannot contribute a scanned build source, so it is simply absent from
        # target provenance rather than being initialized here.
        if not _initialized_repository(worktree):
            continue

        node = {
            "name": dependency["name"],
            "repository": repository,
            "owner_path": "." if owner.resolve() == root.resolve() else _relative(root, owner),
            "dependency_path": Path(dependency["path"]).as_posix(),
            "worktree_path": _relative(root, worktree),
            "declared_ref": dependency["ref"],
            "revision": _git(worktree, "rev-parse", "HEAD"),
            "depth": depth,
        }
        nodes.append(node)
        _collect_dependency_nodes(
            root,
            worktree,
            lineage=(*lineage, repository),
            depth=depth + 1,
            nodes=nodes,
        )


def _source_owner(
    root: Path,
    source: Path,
    dependency_nodes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    resolved = source.resolve()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for node in dependency_nodes:
        worktree = (root / node["worktree_path"]).resolve()
        try:
            resolved.relative_to(worktree)
        except ValueError:
            continue
        candidates.append((len(worktree.parts), node))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def write_dependency_provenance(
    context: ProjectContext,
    manifest: Path,
    output: Path,
) -> Path | None:
    """Write target-level provenance from the already-scanned SCons manifest.

    The SCons manifest remains the source of truth for which files a target used.
    This function only attributes those existing source paths to initialized
    owner-local external worktrees and records their exact revisions.
    """

    try:
        source_revision = resolve_source_revision(context)
    except RuntimeError as exc:
        print(f"WARNING: persistent SCAD dependency provenance skipped: {exc}")
        return None

    if not manifest.is_file():
        raise RuntimeError(f"SCons build manifest does not exist: {manifest}")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid SCons build manifest: {manifest}")

    root = context.root.resolve()
    root_url = _git(root, "remote", "get-url", "origin", check=False) or "local-root"
    dependency_nodes: list[dict[str, Any]] = []
    _collect_dependency_nodes(
        root,
        root,
        lineage=(_normalize_repository_url(root_url),),
        depth=1,
        nodes=dependency_nodes,
    )

    targets: list[dict[str, Any]] = []
    for target in payload.get("targets", []) or []:
        if not isinstance(target, dict):
            continue

        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for raw_source in target.get("sources", []) or []:
            source = Path(str(raw_source))
            if not source.is_absolute():
                source = root / source
            owner = _source_owner(root, source, dependency_nodes)
            if owner is None:
                continue

            key = (
                str(owner["owner_path"]),
                str(owner["dependency_path"]),
                str(owner["revision"]),
            )
            record = grouped.get(key)
            if record is None:
                record = dict(owner)
                record["used_sources"] = []
                grouped[key] = record

            source_value = _relative(root, source)
            if source_value not in record["used_sources"]:
                record["used_sources"].append(source_value)

        dependencies = sorted(
            grouped.values(),
            key=lambda item: (
                item["owner_path"],
                item["dependency_path"],
                item["name"],
            ),
        )
        for dependency in dependencies:
            dependency["used_sources"].sort()

        targets.append(
            {
                "output": str(target.get("output", "")),
                "source": str(target.get("source", "")),
                "dependencies": dependencies,
            }
        )

    try:
        manifest_value = manifest.resolve().relative_to(root).as_posix()
    except ValueError:
        manifest_value = str(manifest.resolve())

    evidence = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "source_revision": source_revision,
        "build_manifest": manifest_value,
        "targets": targets,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
