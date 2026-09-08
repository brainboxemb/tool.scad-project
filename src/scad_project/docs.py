from __future__ import annotations
from pathlib import Path
import re

from .config import ProjectContext
from .process import run_checked

STRUCTURED_RE = re.compile(
    r"^\s*//\s*(Module|Function|Constant|Section|Topic|Example)\s*:",
    re.MULTILINE,
)
FILE_RE = re.compile(r"^\s*//\s*(File|LibFile)\s*:", re.MULTILINE)


def lint_docs(context: ProjectContext, run_docsgen: bool = True) -> list[str]:
    errors: list[str] = []
    root = context.path(context.config["paths"]["design_root"])
    if not root.exists():
        return errors

    ext = (root / "ext").resolve()

    for path in sorted(root.rglob("*.scad")):
        try:
            path.resolve().relative_to(ext)
            continue
        except ValueError:
            pass

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
