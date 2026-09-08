"""Command-line dispatcher for project bootstrap, lint, build and publication."""

from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .build import build_project, check_libraries
from .config import ConfigError, load_context, validate_config
from .design import build_design, lint_design
from .docs import lint_docs
from .publish import publish_build, publish_verification
from .index import write_build_index
from .tooling import tooling_errors
from .verification import run_functional_verification
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
    """Parse one project command and execute it against the nearest project.yml."""

    p = argparse.ArgumentParser(prog="scad-project")
    p.add_argument("--project", type=Path, default=None)
    sub = p.add_subparsers(dest="command", required=True)
    # Keep command registration centralized so --help reflects the real API.
    for name in (
        "config-lint", "externals-check", "externals-status",
        "externals-init", "externals-sync", "externals-deinit",
        "libraries-check", "docs-lint", "design-lint",
        "design-build", "design-render", "build", "verify",
        "functional-verify", "build-index", "tooling-check",
        "publish-build", "publish-verification",
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
        elif args.command == "tooling-check":
            errors = tooling_errors(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print("tooling versions: OK")
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
            renders, errors = lint_design(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            print(f"design renders declared: {len(renders)}")
            print("design documentation: OK")
        # design-render remains a compatibility alias; design-build is canonical.
        elif args.command in {"design-build", "design-render"}:
            build_design(ctx)
            print("design build: OK")
        elif args.command == "build":
            errors = validate_externals_config(ctx) + check_externals(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            build_project(ctx)
            print("build: OK")
        elif args.command == "functional-verify":
            run_functional_verification(ctx)
            print("functional verification: OK")
        elif args.command == "build-index":
            output = write_build_index(ctx)
            print(f"build index: {output.relative_to(ctx.root)}")
        elif args.command == "verify":
            errors = (
                validate_externals_config(ctx)
                + check_externals(ctx)
                + lint_docs(ctx)
            )
            _, design_errors = lint_design(ctx)
            errors += design_errors
            if errors:
                raise RuntimeError("\n".join(errors))
            build_project(ctx)
            print("verify: OK")
        elif args.command == "publish-build":
            publish_build(ctx)
        elif args.command == "publish-verification":
            publish_verification(ctx)

    except (ConfigError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
