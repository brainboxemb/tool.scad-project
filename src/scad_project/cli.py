from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .build import build_project, check_libraries
from .config import ConfigError, load_context, validate_config
from .design import lint_design, render_design
from .docs import lint_docs


def fail(errors):
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1


def main() -> None:
    p = argparse.ArgumentParser(prog="scad-project")
    p.add_argument("--project", type=Path, default=None)
    sub = p.add_subparsers(dest="command", required=True)
    for name in (
        "config-lint", "libraries-check", "docs-lint",
        "design-lint", "design-render", "build", "verify",
    ):
        sub.add_parser(name)

    args = p.parse_args()
    try:
        ctx = load_context(args.project)
        errors = validate_config(ctx)
        if errors:
            raise RuntimeError("\n".join(errors))

        if args.command == "config-lint":
            print("project.yml: OK")
        elif args.command == "libraries-check":
            errors = check_libraries(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print("libraries: OK")
        elif args.command == "docs-lint":
            errors = lint_docs(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print("OpenSCAD docs: OK")
        elif args.command == "design-lint":
            renders, errors, stale = lint_design(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print(f"design renders declared: {len(renders)}")
            for path in stale:
                print(f"WARNING: stale design image: {path.relative_to(ctx.root)}")
            print("design documentation: OK")
        elif args.command == "design-render":
            render_design(ctx)
            print("design renders: OK")
        elif args.command == "build":
            errors = check_libraries(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            build_project(ctx)
            print("build: OK")
        elif args.command == "verify":
            errors = check_libraries(ctx) + lint_docs(ctx)
            _, design_errors, stale = lint_design(ctx)
            errors += design_errors
            if errors:
                raise RuntimeError("\n".join(errors))
            for path in stale:
                print(f"WARNING: stale design image: {path.relative_to(ctx.root)}")
            build_project(ctx)
            print("verify: OK")

    except (ConfigError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
