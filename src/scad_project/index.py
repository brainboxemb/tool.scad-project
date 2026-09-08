"""Generate standardized navigation files for generated build output."""

from __future__ import annotations

from pathlib import Path

from .config import ProjectContext


KNOWN_SECTIONS = (
    ("design", "Design documentation", "design/README.md"),
    ("png", "PNG renders", "png/"),
    ("stl", "STL exports", "stl/"),
)


def write_build_index(context: ProjectContext) -> Path:
    """Write the common root README for the generated build snapshot.

    Only links whose targets currently exist are included. This keeps the
    branch index identical in style across projects without advertising output
    types that a particular project does not generate.
    """

    build_root = context.path(context.config["paths"]["build_root"])
    build_root.mkdir(parents=True, exist_ok=True)

    links: list[tuple[str, str]] = []
    for dirname, label, target in KNOWN_SECTIONS:
        candidate = build_root / dirname
        if candidate.exists():
            links.append((label, target))

    lines = [
        "# Generated build output",
        "",
        "This branch contains generated output for the latest successful project build.",
        "It is generated automatically and should not be edited manually.",
        "",
        "## Contents",
        "",
    ]

    if links:
        lines.extend(f"- [{label}]({target})" for label, target in links)
    else:
        lines.append("- No generated output sections are present.")

    lines += [
        "",
        "## Branch roles",
        "",
        "```text",
        "main",
        "    source code",
        "    source design documentation",
        "    project configuration",
        "",
        "build",
        "    generated design documentation",
        "    generated build output",
        "```",
        "",
        "Files on this branch are replaced by the next successful build publication.",
        "",
    ]

    output = build_root / "README.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
