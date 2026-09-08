"""Run external tools and convert dangerous OpenSCAD warnings into failures."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


# OpenSCAD often returns exit code 0 even when a model contains semantic
# problems. These warnings are considered build/render failures because they
# indicate geometry may have been skipped or transformed with undef values.
OPENSCAD_FATAL_WARNING_PATTERNS = [
    re.compile(r"WARNING:\s+Ignoring unknown variable", re.IGNORECASE),
    re.compile(r"WARNING:\s+undefined operation", re.IGNORECASE),
    re.compile(r"WARNING:\s+Unable to convert .* parameter", re.IGNORECASE),
    re.compile(r"WARNING:.*\bundef(?:ined)?\b", re.IGNORECASE),
]

# Known benign messages that can occur when a design document supplies an
# explicit OpenSCAD viewport through $vpr/$vpt/$vpd.
OPENSCAD_ALLOWED_WARNING_PATTERNS = [
    re.compile(
        r"WARNING:\s+Viewall and autocenter disabled in favor of \$vp\*",
        re.IGNORECASE,
    ),
]


def _check_openscad_output(args: list[str], output: str) -> None:
    command = Path(args[0]).name.lower()

    # xvfb-run is normally the outer command for PNG renders; OpenSCAD is then
    # present later in argv.
    is_openscad = command == "openscad" or any(
        Path(arg).name.lower() == "openscad" for arg in args
    )
    if not is_openscad:
        return

    fatal_lines: list[str] = []

    for line in output.splitlines():
        if "WARNING:" not in line:
            continue

        if any(pattern.search(line) for pattern in OPENSCAD_ALLOWED_WARNING_PATTERNS):
            continue

        if any(pattern.search(line) for pattern in OPENSCAD_FATAL_WARNING_PATTERNS):
            fatal_lines.append(line.strip())

    if fatal_lines:
        details = "\n".join(f"  {line}" for line in fatal_lines)
        raise RuntimeError(
            "OpenSCAD reported warnings that can invalidate geometry:\n" + details
        )


def run_checked(args: list[str], *, cwd: Path) -> None:
    print("+", " ".join(args))

    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {args[0]}") from exc

    if result.stdout:
        print(result.stdout, end="")

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(args)}"
        )

    _check_openscad_output(args, result.stdout or "")
