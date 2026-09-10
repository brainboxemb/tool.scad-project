#!/usr/bin/env python3
"""Generate a compact unit-test overview from test-module docstrings.

The detailed explanation lives in each ``tests/test_*.py`` module. This script
uses Python's AST to read those docstrings without importing or executing the
tests. The generated HTML deliberately shows only the test area, what is
checked, and the source file. Test functions, fixtures, and testing mechanics
remain in the source where maintainers need them.
"""

from __future__ import annotations

import argparse
import ast
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"


def read_entry(path: Path) -> tuple[str, str, str]:
    """Return ``area``, ``checks`` and ``testing approach`` from one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring = ast.get_docstring(tree, clean=True)
    if not docstring:
        raise ValueError(f"{path}: missing module docstring")

    marker_checks = "\n\nChecks:\n"
    marker_approach = "\n\nTesting approach:\n"
    if marker_checks not in docstring or marker_approach not in docstring:
        raise ValueError(
            f"{path}: module docstring must use the sections 'Checks:' and "
            "'Testing approach:'"
        )

    area, remainder = docstring.split(marker_checks, 1)
    checks, approach = remainder.split(marker_approach, 1)
    area = area.strip()
    checks = checks.strip()
    approach = approach.strip()
    if not area or not checks or not approach:
        raise ValueError(f"{path}: test documentation sections may not be empty")
    return area, checks, approach


def _cell(text: str) -> str:
    """Escape source text and join wrapped source lines for an HTML table cell."""
    return html.escape(text).replace("\n", " ")


def render_reference(entries: list[tuple[str, str, str]]) -> str:
    """Render the quick-reference table."""
    rows = []
    for source, area, checks in entries:
        rows.append(
            "<tr>"
            f"<td><strong>{_cell(area)}</strong></td>"
            f"<td>{_cell(checks)}</td>"
            f"<td><code>{html.escape(source)}</code></td>"
            "</tr>"
        )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tool.scad-project unit test overview</title>
<style>
body { font-family: system-ui, sans-serif; line-height: 1.45; margin: 2rem; max-width: 1400px; }
h1 { margin-bottom: .4rem; }
p.intro { max-width: 950px; }
table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
th, td { border: 1px solid #bbb; padding: .75rem .85rem; text-align: left; vertical-align: top; }
th { position: sticky; top: 0; background: Canvas; }
td:first-child { width: 20%; }
td:nth-child(2) { width: 65%; }
td:last-child { width: 15%; white-space: nowrap; }
code { font-size: .9em; }
</style>
</head>
<body>
<h1>Unit test overview</h1>
<p class="intro">This page is a quick inventory of the behavior protected by the unit-test suite. The descriptions come directly from the module docstrings in <code>tests/test_*.py</code>. Open the source file for the detailed testing approach and implementation notes.</p>
<table>
<thead><tr><th>Area</th><th>What is checked</th><th>Source</th></tr></thead>
<tbody>
""" + "\n".join(rows) + """
</tbody>
</table>
</body>
</html>
"""


def generate(output: Path) -> None:
    """Read all test modules and write one compact HTML overview."""
    entries: list[tuple[str, str, str]] = []
    for path in sorted(TEST_ROOT.glob("test_*.py")):
        area, checks, _approach = read_entry(path)
        entries.append((path.name, area, checks))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_reference(entries), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "bld" / "test-docs" / "index.html",
    )
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
