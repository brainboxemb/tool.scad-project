"""Command-line dispatcher for project bootstrap, lint, build and publication."""

from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .build import check_libraries
from .build_engine import build_project
from .build_engine_config import validate_build_engine_config
from .config import ConfigError, load_context, validate_config
from .design_policy import build_design, lint_design
from .docs import lint_docs
from .publish import publish_build, publish_verification, write_publication_info
from .release import package_release, publish_release_branches
from .index import write_build_index
from .tooling import tooling_errors
from .verification import run_functional_verification
from .dependencies import (
    dependency_status,
    repo_sync,
    repo_update,
    validate_dependency_config,
)
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
        "publication-info-build", "publication-info-verification",
        "publish-build", "publish-verification",
        "repo-sync", "repo-update", "repo-status",
    ):
        sub.add_parser(name)

    release_package = sub.add_parser("release-package")
    release_package.add_argument("--version", required=True)
    release_package.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for release ZIPs and SHA256SUMS.txt",
    )

    release_publish = sub.add_parser("release-publish-branches")
    release_publish.add_argument("--version", required=True)
    release_publish.add_argument("--source-sha", required=True)

    args = p.parse_args()
    try:
        ctx = load_context(args.project)
        errors = validate_config(ctx) + validate_build_engine_config(ctx)
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
        elif args.command == "repo-sync":
            repo_sync(ctx)
            print("repository dependencies: synchronized")
        elif args.command == "repo-update":
            repo_update(ctx)
            print("repository dependencies: update complete")
        elif args.command == "repo-status":
            errors = validate_dependency_config(ctx)
            if errors:
                raise RuntimeError("\n".join(errors))
            for row in dependency_status(ctx):
                print(
                    f"{row['role']}: {row['name']} "
                    f"ref={row['ref']} commit={row['commit']} path={row['path']}"
                )
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
        elif args.command == "publication-info-build":
            output = write_publication_info(ctx, "build")
            print(f"publication info: {output.relative_to(ctx.root)}")
        elif args.command == "publication-info-verification":
            output = write_publication_info(ctx, "verification")
            print(f"publication info: {output.relative_to(ctx.root)}")
        elif args.command == "publish-build":
            publish_build(ctx)
        elif args.command == "publish-verification":
            publish_verification(ctx)
        elif args.command == "release-package":
            artifacts = package_release(ctx, args.version, args.output_dir)
            print(f"release package: {artifacts.version}")
            for asset in artifacts.assets:
                print(f"  {asset.relative_to(ctx.root) if asset.is_relative_to(ctx.root) else asset}")
        elif args.command == "release-publish-branches":
            branches = publish_release_branches(ctx, args.version, args.source_sha)
            print(f"release build branch: {branches.build_branch}")
            print(f"release verification branch: {branches.verification_branch}")

    except (ConfigError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
