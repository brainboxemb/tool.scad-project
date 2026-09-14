"""Command-line dispatcher for SCAD project lint, build and publication."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .build import check_libraries
from . import build_decision_audit
from .build_engine import build_project
from .build_engine_config import validate_build_engine_config
from .config import ConfigError, load_context, validate_config
from .design_policy import build_design, lint_design
from .docs import lint_docs
from .producer import produce_build, produce_verification
from .publish import (
    cleanup_pull_request_publication,
    publish_build,
    publish_verification,
    write_publication_info,
)
from .release import package_release, publish_release_branches
from .release_config import validate_release_config
from .release_notes import write_release_notes
from .index import write_build_index
from .tooling import tooling_errors
from .verification import run_functional_verification
from .repository import (
    repo_status,
    repo_sync,
    repo_update,
    repository_validate,
    sync_workflow_refs,
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


def _project_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _audit_changed_paths(root: Path, args) -> list[str]:
    direct = list(args.changed_path or [])
    files = list(args.changed_paths_file or [])
    if not direct and not files:
        raise RuntimeError(
            "build-audit requires --changed-path and/or --changed-paths-file"
        )

    values = direct
    for configured in files:
        path = _project_path(root, configured)
        if not path.is_file():
            raise RuntimeError(f"changed-paths file does not exist: {path}")
        values.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return values


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
        "produce-build", "produce-verification",
        "build-index", "tooling-check",
        "publication-info-build", "publication-info-verification",
        "publish-build", "publish-verification",
        "repo-sync", "repo-update", "repo-status", "workflow-sync",
    ):
        sub.add_parser(name)

    build_audit = sub.add_parser("build-audit")
    build_audit.add_argument("--report", type=Path, required=True)
    build_audit.add_argument("--changed-path", action="append", default=[])
    build_audit.add_argument(
        "--changed-paths-file", type=Path, action="append", default=[]
    )
    build_audit.add_argument("--output", type=Path, default=None)

    publication_cleanup = sub.add_parser("publication-cleanup-pr")
    publication_cleanup.add_argument("--pr-number", type=int, required=True)

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

    release_notes = sub.add_parser("release-notes")
    release_notes.add_argument("--version", required=True)
    release_notes.add_argument("--source-sha", required=True)
    release_notes.add_argument("--output", type=Path, required=True)
    release_notes.add_argument("--repository", default=None)

    args = p.parse_args()
    try:
        ctx = load_context(args.project)
        errors = (
            validate_config(ctx)
            + validate_build_engine_config(ctx)
            + validate_release_config(ctx)
        )
        if errors:
            raise RuntimeError("\n".join(errors))

        if args.command == "config-lint":
            repository_validate(ctx)
            print(f"{ctx.config_file.name}: OK")
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
            print("repository dependencies: synchronized by tool.git-project")
        elif args.command == "repo-update":
            repo_update(ctx)
            print("repository dependencies: update complete")
        elif args.command == "repo-status":
            repo_status(ctx)
        elif args.command == "workflow-sync":
            sync_workflow_refs(ctx)
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
        elif args.command == "build-audit":
            report_path = _project_path(ctx.root, args.report)
            if not report_path.is_file():
                raise RuntimeError(f"build-decision report does not exist: {report_path}")
            try:
                decision_report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid build-decision report JSON: {report_path}: {exc}"
                ) from exc

            changed_paths = _audit_changed_paths(ctx.root, args)
            output_path = (
                _project_path(ctx.root, args.output)
                if args.output is not None
                else report_path.with_name(f"{report_path.stem}-audit.json")
            )
            audit = build_decision_audit.write_audit_report(
                decision_report=decision_report,
                changed_paths=changed_paths,
                output_path=output_path,
            )
            build_decision_audit.print_audit_summary(audit)
            print(
                f"build audit report: "
                f"{output_path.relative_to(ctx.root) if output_path.is_relative_to(ctx.root) else output_path}"
            )
            if audit["result"] == "FAIL":
                raise SystemExit(1)
        elif args.command == "produce-build":
            produce_build(ctx)
            print("build producer: OK")
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
            run_functional_verification(ctx)
            print("verify: OK")
        elif args.command == "produce-verification":
            produce_verification(ctx)
            print("verification producer: OK")
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
        elif args.command == "publication-cleanup-pr":
            removed = cleanup_pull_request_publication(ctx, args.pr_number)
            if removed:
                for branch in removed:
                    print(f"Removed pull-request publication branch: {branch}")
            else:
                print(f"No pull-request publication branches found for PR #{args.pr_number}")
        elif args.command == "release-package":
            artifacts = package_release(ctx, args.version, args.output_dir)
            print(f"release package: {artifacts.version}")
            for asset in artifacts.assets:
                print(f"  {asset.relative_to(ctx.root) if asset.is_relative_to(ctx.root) else asset}")
        elif args.command == "release-publish-branches":
            branches = publish_release_branches(ctx, args.version, args.source_sha)
            print(f"release build branch: {branches.build_branch}")
            print(f"release verification branch: {branches.verification_branch}")
        elif args.command == "release-notes":
            output = write_release_notes(
                ctx,
                args.version,
                args.source_sha,
                args.output,
                repository=args.repository,
            )
            print(f"release notes: {output.relative_to(ctx.root) if output.is_relative_to(ctx.root) else output}")

    except (ConfigError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
