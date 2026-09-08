from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .build import build_project, check_libraries
from .config import ConfigError, load_context, validate_config
from .design import lint_design, render_design
from .docs import lint_docs
from .externals import (
    check_externals,
    deinit_externals,
    external_status,
    init_externals,
    sync_externals,
    validate_externals_config,
)


def fail(errors):
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1


def main() -> None:
    p = argparse.ArgumentParser(prog="scad-project")
    p.add_argument("--project", type=Path, default=None)
    sub = p.add_subparsers(dest="command", required=True)
    for name in (
        "config-lint", "externals-check", "externals-status",
        "externals-init", "externals-sync", "externals-deinit",
        "libraries-check", "docs-lint", "design-lint",
        "design-render", "build", "verify",
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
        elif args.command in {"externals-check", "libraries-check"}:
            errors = validate_externals_config(ctx) + check_externals(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print("externals: OK")
        elif args.command == "externals-status":
            errors = validate_externals_config(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            rows = external_status(ctx)
            if not rows:
                print("No externals configured.")
            for row in rows:
                print(
                    f"{row['name']}: {row['state']} "
                    f"[{row['commit']}] {row['path']}"
                )
        elif args.command == "externals-init":
            init_externals(ctx)
            print("externals initialized")
        elif args.command == "externals-sync":
            sync_externals(ctx)
            print("externals synchronized")
        elif args.command == "externals-deinit":
            deinit_externals(ctx)
            print("externals deinitialized")
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
            errors = validate_externals_config(ctx) + check_externals(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            build_project(ctx)
            print("build: OK")
        elif args.command == "verify":
            errors = (
                validate_externals_config(ctx)
                + check_externals(ctx)
                + lint_docs(ctx)
            )
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
