"""Discover static file dependencies in OpenSCAD sources.

The scanner is intentionally small and independent from SCons. SCons consumes
its result as explicit source dependencies while the same scanner remains easy
to unit-test without invoking a build engine.

Source dependencies declared through ``use``/``include`` are followed
recursively. Static file references through ``import``/``surface`` are treated
as leaf dependencies. Dynamic file expressions are rejected rather than being
silently omitted from a cache signature.
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
_FILE_CALL_RE = re.compile(
    r"\b(import(?:_(?:stl|dxf|off))?|surface)\s*\(",
    re.IGNORECASE,
)
_NAMED_FILE_RE = re.compile(r'\bfile\s*=\s*"([^"\r\n]+)"', re.IGNORECASE)
_POSITIONAL_FILE_RE = re.compile(r'^\s*"([^"\r\n]+)"')


class OpenScadDependencyError(RuntimeError):
    """Raised when an OpenSCAD dependency cannot be resolved safely."""


def _without_comments(text: str) -> str:
    """Remove block and line comments before looking for dependencies."""

    text = _BLOCK_COMMENT_RE.sub("", text)
    return _LINE_COMMENT_RE.sub("", text)


def _call_arguments(text: str, open_paren: int) -> str:
    """Return text inside one balanced OpenSCAD function call."""

    depth = 0
    in_string = False
    escaped = False

    for index in range(open_paren, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1:index]

    raise OpenScadDependencyError("Unterminated OpenSCAD file-loading call")


def _file_references(text: str, *, owner: Path) -> list[tuple[int, str]]:
    """Return static ``import``/``surface`` references with source positions."""

    references: list[tuple[int, str]] = []
    for match in _FILE_CALL_RE.finditer(text):
        arguments = _call_arguments(text, match.end() - 1)
        named = _NAMED_FILE_RE.search(arguments)
        positional = _POSITIONAL_FILE_RE.match(arguments)
        file_match = named or positional
        if file_match is None:
            call_name = match.group(1)
            raise OpenScadDependencyError(
                f"Cannot safely determine static file dependency for "
                f"{call_name}() in {owner}; use a literal file path or the "
                "direct build engine"
            )
        references.append((match.start(), file_match.group(1).strip()))
    return references


def referenced_openscad_paths(source: Path) -> list[str]:
    """Return raw ``use``/``include`` paths in source order."""

    text = _without_comments(source.read_text(encoding="utf-8"))
    return [match.group(1).strip() for match in _DIRECTIVE_RE.finditer(text)]


def referenced_file_paths(source: Path) -> list[str]:
    """Return static ``import``/``surface`` file paths in source order."""

    text = _without_comments(source.read_text(encoding="utf-8"))
    return [reference for _, reference in _file_references(text, owner=source)]


def _reference_specs(source: Path) -> list[tuple[str, bool]]:
    """Return ``(path, recurse)`` references in deterministic source order."""

    text = _without_comments(source.read_text(encoding="utf-8"))
    references: list[tuple[int, str, bool]] = [
        (match.start(), match.group(1).strip(), True)
        for match in _DIRECTIVE_RE.finditer(text)
    ]
    references.extend(
        (position, reference, False)
        for position, reference in _file_references(text, owner=source)
    )
    references.sort(key=lambda item: item[0])
    return [(reference, recurse) for _, reference, recurse in references]


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


def _resolved_references(
    source: Path,
    *,
    search_paths: Iterable[Path] = (),
) -> list[tuple[Path, bool]]:
    source = source.resolve()
    roots = tuple(Path(path).resolve() for path in search_paths)
    result: list[tuple[Path, bool]] = []
    seen: set[Path] = set()

    for reference, recurse in _reference_specs(source):
        dependency = _resolve_reference(source, reference, roots)
        if dependency not in seen:
            seen.add(dependency)
            result.append((dependency, recurse))

    return result


def direct_openscad_dependencies(
    source: Path,
    *,
    search_paths: Iterable[Path] = (),
) -> list[Path]:
    """Resolve all static dependencies referenced directly by ``source``."""

    return [
        dependency
        for dependency, _ in _resolved_references(
            source,
            search_paths=search_paths,
        )
    ]


def scan_openscad_dependencies(
    source: Path,
    *,
    search_paths: Iterable[Path] = (),
) -> list[Path]:
    """Return all static OpenSCAD dependencies in deterministic DFS order.

    ``use``/``include`` sources are followed transitively. Imported assets are
    leaf dependencies. The root source is never returned, and cycles/repeated
    references are safe: every dependency appears at most once.
    """

    root = source.resolve()
    roots = tuple(Path(path).resolve() for path in search_paths)
    seen: set[Path] = {root}
    result: list[Path] = []

    def visit(current: Path) -> None:
        for dependency, recurse in _resolved_references(
            current,
            search_paths=roots,
        ):
            if dependency in seen:
                continue
            seen.add(dependency)
            result.append(dependency)
            if recurse:
                visit(dependency)

    visit(root)
    return result
