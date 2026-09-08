"""Resolve and update versioned Git-submodule dependencies.

`project.yml` describes dependency policy. Parent-repository gitlinks remain the
lock that makes a normal clone/repo-sync reproducible.

Supported refs:

- ``vX.Y.Z`` (or another explicit tag): exact tag
- ``latest``: newest stable semantic-version tag
- branch name such as ``main``: current remote branch head

`repo-sync` restores committed gitlinks.
`repo-update` intentionally resolves configured refs and leaves changed gitlinks
and workflow callers uncommitted for review.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

import yaml

from .config import ProjectContext
from .externals import configured_externals
from .process import run_checked


SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
WORKFLOW_USE_RE = re.compile(
    r"(brainboxemb/tool\.scad-project/\.github/workflows/"
    r"(?:project-build|project-verify)\.yml)@([^\s\"']+)"
)


@dataclass(frozen=True)
class Dependency:
    name: str
    kind: str
    url: str
    path: str
    ref: str
    role: str

    def root(self, context: ProjectContext) -> Path:
        return context.path(self.path)


def _tooling_dependency(context: ProjectContext) -> Dependency | None:
    raw = context.config.get("tooling")
    if not raw:
        return None
    if not isinstance(raw, dict):
        return None

    modern = raw.get("tool_scad_project")
    if isinstance(modern, dict):
        return Dependency(
            name="tool.scad-project",
            kind=modern.get("type", "git-submodule"),
            url=modern.get(
                "url",
                "https://github.com/brainboxemb/tool.scad-project.git",
            ),
            path=modern.get("path", "tools/tool.scad-project"),
            ref=str(modern.get("ref", "")).strip(),
            role="tooling",
        )

    # v0.4.1 compatibility while consumers migrate.
    legacy = raw.get("tool_scad_project_version")
    if legacy:
        return Dependency(
            name="tool.scad-project",
            kind="git-submodule",
            url="https://github.com/brainboxemb/tool.scad-project.git",
            path="tools/tool.scad-project",
            ref=str(legacy).strip(),
            role="tooling",
        )

    return None


def configured_dependencies(context: ProjectContext) -> list[Dependency]:
    """Return tooling first, then configured external libraries."""

    result: list[Dependency] = []
    tooling = _tooling_dependency(context)
    if tooling:
        result.append(tooling)

    for external in configured_externals(context):
        result.append(
            Dependency(
                name=external.name,
                kind=external.kind,
                url=external.url,
                path=external.path,
                ref=(external.ref or "").strip(),
                role="external",
            )
        )
    return result


def validate_dependency_config(context: ProjectContext) -> list[str]:
    """Validate version/ref metadata shared by tooling and libraries."""

    errors: list[str] = []
    dependencies = configured_dependencies(context)
    seen_paths: set[str] = set()

    tooling = context.config.get("tooling")
    if tooling is not None:
        if not isinstance(tooling, dict):
            errors.append("tooling must be a mapping")
        else:
            modern = tooling.get("tool_scad_project")
            legacy = tooling.get("tool_scad_project_version")
            if modern is None and legacy is None:
                errors.append(
                    "tooling requires tool_scad_project or "
                    "tool_scad_project_version"
                )
            if modern is not None:
                if not isinstance(modern, dict):
                    errors.append("tooling.tool_scad_project must be a mapping")
                else:
                    if not modern.get("ref"):
                        errors.append("tooling.tool_scad_project.ref is required")
                    if modern.get("type", "git-submodule") != "git-submodule":
                        errors.append(
                            "tooling.tool_scad_project.type must be git-submodule"
                        )

    for dep in dependencies:
        normalized = dep.path.replace("\\", "/").rstrip("/")
        if normalized in seen_paths:
            errors.append(f"Duplicate dependency path: {normalized}")
        seen_paths.add(normalized)

        if dep.kind != "git-submodule":
            errors.append(
                f"Dependency {dep.name}: unsupported type {dep.kind!r}"
            )
        if not dep.url:
            errors.append(f"Dependency {dep.name}: url is required")
        if not dep.ref:
            errors.append(f"Dependency {dep.name}: ref is required")
        if Path(normalized).is_absolute() or normalized.startswith("../"):
            errors.append(
                f"Dependency {dep.name}: path must stay inside project: {dep.path}"
            )

    return errors


def _git_output(context: ProjectContext, args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or context.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _is_clean(context: ProjectContext, dep: Dependency) -> bool:
    root = dep.root(context)
    if not root.exists():
        return True
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        cwd=context.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _ensure_registered(context: ProjectContext, dep: Dependency) -> None:
    path = dep.path.replace("\\", "/").rstrip("/")
    mode_line = subprocess.run(
        ["git", "ls-files", "--stage", "--", path],
        cwd=context.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout

    if mode_line.startswith("160000 "):
        return

    target = dep.root(context)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and any(target.iterdir()):
        # Reuse an interrupted/previous Git checkout only.
        probe = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--git-dir"],
            cwd=context.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                f"Cannot register {dep.name}: target contains non-Git files: {path}"
            )
    elif target.exists():
        target.rmdir()

    run_checked(
        ["git", "submodule", "add", "--force", dep.url, path],
        cwd=context.root,
    )


def _stable_semver_tags(context: ProjectContext, dep: Dependency) -> list[tuple[tuple[int, int, int], str]]:
    output = _git_output(
        context,
        ["-C", str(dep.root(context)), "tag", "--list"],
    )
    parsed: list[tuple[tuple[int, int, int], str]] = []
    for tag in output.splitlines():
        match = SEMVER_TAG_RE.fullmatch(tag.strip())
        if match:
            parsed.append((tuple(int(v) for v in match.groups()), tag.strip()))
    return sorted(parsed)


def _resolve_ref(context: ProjectContext, dep: Dependency) -> tuple[str, str]:
    """Return (git ref to checkout, workflow ref when this is tooling)."""

    root = dep.root(context)
    run_checked(["git", "-C", str(root), "fetch", "--prune", "--tags", "origin"],
                cwd=context.root)

    requested = dep.ref.strip()
    if requested == "latest":
        tags = _stable_semver_tags(context, dep)
        if not tags:
            raise RuntimeError(
                f"Dependency {dep.name}: ref 'latest' found no stable vX.Y.Z tags"
            )
        tag = tags[-1][1]
        return tag, tag

    # Exact local/remote tag wins over same-named branch.
    tag_probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"refs/tags/{requested}^{{commit}}"],
        cwd=context.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if tag_probe.returncode == 0:
        return requested, requested

    branch_probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"refs/remotes/origin/{requested}^{{commit}}"],
        cwd=context.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if branch_probe.returncode == 0:
        return f"origin/{requested}", requested

    raise RuntimeError(
        f"Dependency {dep.name}: configured ref {requested!r} is neither a tag "
        "nor a branch on origin"
    )


def _checkout_dependency(context: ProjectContext, dep: Dependency) -> dict[str, str]:
    if not _is_clean(context, dep):
        raise RuntimeError(
            f"Dependency {dep.name} has local changes: {dep.path}"
        )

    old = _git_output(
        context,
        ["-C", str(dep.root(context)), "rev-parse", "HEAD"],
    )
    checkout_ref, workflow_ref = _resolve_ref(context, dep)

    # Detached checkout is deliberate for both tags and branch heads: the parent
    # gitlink is the lock, while project.yml keeps the update policy.
    run_checked(
        ["git", "-C", str(dep.root(context)), "checkout", "--detach", checkout_ref],
        cwd=context.root,
    )

    new = _git_output(
        context,
        ["-C", str(dep.root(context)), "rev-parse", "HEAD"],
    )
    return {
        "name": dep.name,
        "path": dep.path,
        "requested": dep.ref,
        "resolved": workflow_ref,
        "old": old,
        "new": new,
        "changed": "yes" if old != new else "no",
    }


def _rewrite_tool_workflow_refs(context: ProjectContext, resolved_ref: str) -> list[Path]:
    """Keep thin consumer workflows aligned with the resolved tooling ref."""

    workflow_dir = context.root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []

    changed: list[Path] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        new_text = WORKFLOW_USE_RE.sub(
            lambda m: f"{m.group(1)}@{resolved_ref}",
            text,
        )
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(path)
    return changed


def repo_sync(context: ProjectContext) -> None:
    """Restore the exact dependency commits recorded by parent gitlinks."""

    errors = validate_dependency_config(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    for dep in configured_dependencies(context):
        _ensure_registered(context, dep)

    run_checked(["git", "submodule", "sync", "--recursive"], cwd=context.root)
    run_checked(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=context.root,
    )
    print("Repository dependencies restored from committed gitlinks.")


def repo_update(context: ProjectContext) -> list[dict[str, str]]:
    """Resolve configured refs and intentionally advance dependency gitlinks."""

    errors = validate_dependency_config(context)
    if errors:
        raise RuntimeError("\n".join(errors))

    dependencies = configured_dependencies(context)
    for dep in dependencies:
        _ensure_registered(context, dep)

    run_checked(["git", "submodule", "sync", "--recursive"], cwd=context.root)
    run_checked(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=context.root,
    )

    # Update ordinary libraries first. Update the running tool last so the
    # current process has already loaded all code it needs from its checkout.
    ordered = [d for d in dependencies if d.role != "tooling"] + [
        d for d in dependencies if d.role == "tooling"
    ]

    results: list[dict[str, str]] = []
    tooling_resolved: str | None = None
    for dep in ordered:
        result = _checkout_dependency(context, dep)
        results.append(result)
        if dep.role == "tooling":
            tooling_resolved = result["resolved"]

    workflow_changes: list[Path] = []
    if tooling_resolved:
        workflow_changes = _rewrite_tool_workflow_refs(context, tooling_resolved)

    print("")
    print("Repository dependency update")
    print("============================")
    for result in results:
        state = "updated" if result["changed"] == "yes" else "unchanged"
        print(
            f"{result['name']}: {result['requested']} -> "
            f"{result['resolved']} ({state})"
        )
        print(f"  {result['old'][:12]} -> {result['new'][:12]}")
        print(f"  {result['path']}")

    if workflow_changes:
        print("")
        print("Updated reusable workflow refs:")
        for path in workflow_changes:
            print(f"  {path.relative_to(context.root)}")

    print("")
    print("Changes are intentionally left uncommitted for review.")
    run_checked(["git", "status", "--short"], cwd=context.root)
    return results


def dependency_status(context: ProjectContext) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dep in configured_dependencies(context):
        root = dep.root(context)
        commit = "-"
        if root.exists():
            proc = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                cwd=context.root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if proc.returncode == 0:
                commit = proc.stdout.strip()
        rows.append(
            {
                "name": dep.name,
                "role": dep.role,
                "ref": dep.ref,
                "path": dep.path,
                "commit": commit,
            }
        )
    return rows
