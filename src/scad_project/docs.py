"""Lint structured OpenSCAD source documentation with openscad-docsgen."""

from __future__ import annotations
from pathlib import Path
import re

from .config import ProjectContext
from .externals import configured_externals
from .process import run_checked

STRUCTURED_RE = re.compile(
    r"^\s*//\s*(Module|Function|Constant|Section|Topic|Example)\s*:",
    re.MULTILINE,
)
FILE_RE = re.compile(r"^\s*//\s*(File|LibFile)\s*:", re.MULTILINE)


def _design_roots(context: ProjectContext) -> list[Path]:
    paths = context.config["paths"]
    roots = paths.get("design_roots")
    if roots:
        return [context.path(value) for value in roots]
    return [context.path(paths["design_root"])]


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def lint_docs(context: ProjectContext, run_docsgen: bool = True) -> list[str]:
    """Lint structured comments below project design roots only."""

    errors: list[str] = []
    external_roots = [external.root(context).resolve() for external in configured_externals(context)]
    seen: set[Path] = set()

    for root in _design_roots(context):
        if not root.exists():
            continue

        for path in sorted(root.rglob("*.scad")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            if any(_inside(resolved, external_root) for external_root in external_roots):
                continue

            text = path.read_text(encoding="utf-8", errors="replace")
            structured = bool(STRUCTURED_RE.search(text))

            if structured and not FILE_RE.search(text):
                errors.append(
                    f"{path.relative_to(context.root)}: structured docs require "
                    "// File: or // LibFile:"
                )
                continue

            if structured and run_docsgen:
                try:
                    run_checked(
                        ["openscad-docsgen", "-m", "-T", str(path)],
                        cwd=context.root,
                    )
                except RuntimeError as exc:
                    errors.append(f"{path.relative_to(context.root)}: {exc}")

    return errors
