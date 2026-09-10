"""Generate standardized navigation files for generated build output."""

from __future__ import annotations

from pathlib import Path

from .config import ProjectContext
from .publish import resolve_publication_target


KNOWN_SECTIONS = (
    ("design", "Design documentation", "design/README.md"),
    ("png", "PNG renders", "png/README.md"),
    ("stl", "STL exports", "stl/"),
)


def _png_title(relative_path: Path) -> str:
    """Return a readable title for one PNG path."""

    text = relative_path.with_suffix("").as_posix()
    return text.replace("/", " / ").replace("-", " ").replace("_", " ").title()


def write_png_index(png_root: Path) -> Path:
    """Write a browseable Markdown gallery for generated PNG output."""

    png_root.mkdir(parents=True, exist_ok=True)
    images = sorted(
        path.relative_to(png_root)
        for path in png_root.rglob("*.png")
        if path.is_file()
    )

    lines = [
        "# PNG renders",
        "",
        "This gallery is generated automatically from the PNG output in this build snapshot.",
        "Do not edit it manually.",
        "",
    ]

    if images:
        for image in images:
            title = _png_title(image)
            target = image.as_posix()
            lines.extend(
                [
                    f"## {title}",
                    "",
                    f"![{title}]({target})",
                    "",
                ]
            )
    else:
        lines.extend(["No PNG renders are present.", ""])

    output = png_root / "README.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def write_build_index(context: ProjectContext) -> Path:
    """Write the common navigation files for a generated build snapshot.

    Only links whose targets currently exist are included. Publication details
    are resolved from the same policy used by the publisher so mutable
    production snapshots and immutable release snapshots describe themselves
    correctly.
    """

    build_root = context.path(context.config["paths"]["build_root"])
    build_root.mkdir(parents=True, exist_ok=True)

    png_root = build_root / "png"
    if png_root.exists():
        write_png_index(png_root)

    links: list[tuple[str, str]] = []
    for dirname, label, target in KNOWN_SECTIONS:
        candidate = build_root / dirname
        if candidate.exists():
            links.append((label, target))

    publication = resolve_publication_target(context, "build")
    if publication.branch:
        branch_text = f"`{publication.branch}`"
    else:
        branch_text = "artifact only (no generated branch)"

    if publication.immutable:
        policy_text = "immutable release snapshot; never replaced or force-pushed"
    elif publication.publish:
        policy_text = "mutable snapshot; replaced by the next successful publication"
    else:
        policy_text = "artifact-only output; not published to a generated branch"

    lines = [
        "# Generated build output",
        "",
        "This directory contains generated output for a successful project build.",
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
        "## Publication",
        "",
        f"- Context: `{publication.context}`",
        f"- Source: {publication.source_ref_type} `{publication.source_ref}`",
        f"- Generated branch: {branch_text}",
        f"- Policy: {policy_text}",
        "",
        "See `publication-info.txt` for the exact source commit, tooling and runtime provenance.",
        "",
    ]

    output = build_root / "README.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
