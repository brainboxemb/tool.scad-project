"""Discover ``use`` and ``include`` dependencies in OpenSCAD sources.

The scanner is intentionally small and independent from SCons.  SCons can use
its result as explicit source dependencies while the same scanner remains easy
to unit-test without invoking a build engine.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable


_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\r\n]*")
_DIRECTIVE_RE = re.compile(
    r"\b(?:use|include)\s*<\s*([^>\r\n]+?)\s*>",
    re.IGNORECASE,
)


class OpenScadDependencyError(RuntimeError):
    """Raised when a referenced OpenSCAD dependency cannot be resolved."""


def _without_comments(text: str) -> str:
    """Remove block and line comments before looking for directives."""

    text = _BLOCK_COMMENT_RE.sub("", text)
    return _LINE_COMMENT_RE.sub("", text)


def referenced_openscad_paths(source: Path) -> list[str]:
    """Return raw ``use``/``include`` paths in source order."""

    text = source.read_text(encoding="utf-8")
    return [match.group(1).strip() for match in _DIRECTIVE_RE.finditer(_without_comments(text))]


def _resolve_reference(
    owner: Path,
    reference: str,
    search_paths: tuple[Path, ...],
) -> Path:
    raw = Path(reference)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(owner.parent / raw)
        candidates.extend(root / raw for root in search_paths)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    searched = ", ".join(str(path) for path in candidates)
    raise OpenScadDependencyError(
        f"Cannot resolve OpenSCAD dependency {reference!r} referenced by "
        f"{owner}; searched: {searched}"
    )


def direct_openscad_dependencies(
    source: Path,
    *,
    search_paths: Iterable[Path] = (),
) -> list[Path]:
    """Resolve the dependencies referenced directly by ``source``.

    Resolution first follows OpenSCAD's common relative-file pattern and then
    tries the supplied search roots. Duplicate references collapse while source
    order is preserved.
    """

    source = source.resolve()
    roots = tuple(Path(path).resolve() for path in search_paths)
    result: list[Path] = []
    seen: set[Path] = set()

    for reference in referenced_openscad_paths(source):
        dependency = _resolve_reference(source, reference, roots)
        if dependency not in seen:
            seen.add(dependency)
            result.append(dependency)

    return result


def scan_openscad_dependencies(
    source: Path,
    *,
    search_paths: Iterable[Path] = (),
) -> list[Path]:
    """Return all transitive OpenSCAD dependencies in deterministic DFS order.

    The root source is never returned. Cycles and repeated includes are safe:
    every dependency appears at most once.
    """

    root = source.resolve()
    roots = tuple(Path(path).resolve() for path in search_paths)
    seen: set[Path] = {root}
    result: list[Path] = []

    def visit(current: Path) -> None:
        for dependency in direct_openscad_dependencies(
            current,
            search_paths=roots,
        ):
            if dependency in seen:
                continue
            seen.add(dependency)
            result.append(dependency)
            visit(dependency)

    visit(root)
    return result
