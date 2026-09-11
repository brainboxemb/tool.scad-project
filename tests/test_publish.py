"""Publication routing and snapshot safety

Checks:
Builds and verification results go to the correct production, pull-request, tag or
release destination. Ordinary feature-branch pushes are artifact-only by default so
parallel changes cannot overwrite one shared development snapshot. Pull requests publish
into their own mutable dev/pr-N branches, and closing a pull request can remove those
branches. Publication metadata must record the real source commit.

Testing approach:
Most tests supply a small dictionary that represents the GitHub event environment and
inspect the publication decision or generated provenance text. Tests that would
otherwise run `git push` use pytest's `monkeypatch` fixture to temporarily replace the
Git command runner and remote-branch check with recorders. That lets the test verify the
exact Git operation without changing a real remote repository; pytest restores the
original functions afterwards.
"""

from pathlib import Path

import pytest

from scad_project.config import ProjectContext
import scad_project.publish as publish_module
from scad_project.publish import (
    cleanup_pull_request_publication,
    publication_info_text,
    pull_request_publication_branches,
    resolve_publication_target,
    resolve_release_publication_target,
    write_publication_info,
)


def context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "verification": {"output_root": "vrf/out"},
            "publication": {
                "production": {"source_branch": "main"},
                "development": {"pr_branch_prefix": "dev/pr"},
                "release": {
                    "branch_prefix": "rel",
                    "tag_pattern": "v*",
                },
                "tags": {"pattern": "v*"},
            },
        },
    )


def test_main_uses_production_branch_defaults(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
    }
    assert resolve_publication_target(ctx, "build", env).branch == "prod/build"
    assert (
        resolve_publication_target(ctx, "verification", env).branch
        == "prod/verification"
    )


def test_explicit_production_branch_configuration_still_works(tmp_path: Path):
    ctx = context(tmp_path)
    ctx.config["publication"]["production"].update(
        {
            "build_branch": "build",
            "verification_branch": "verification",
        }
    )
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
    }
    assert resolve_publication_target(ctx, "build", env).branch == "build"
    assert resolve_publication_target(ctx, "verification", env).branch == "verification"


def test_feature_branch_is_artifact_only_by_default(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "feature/example",
    }
    target = resolve_publication_target(ctx, "build", env)
    assert target.context == "development"
    assert target.publish is False
    assert target.branch is None
    assert target.immutable is False


def test_feature_branch_can_opt_into_legacy_shared_development_branch(tmp_path: Path):
    ctx = context(tmp_path)
    ctx.config["publication"]["development"].update(
        {
            "publish_branch_pushes": True,
            "build_branch": "dev/build",
        }
    )
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "feature/example",
    }
    target = resolve_publication_target(ctx, "build", env)
    assert target.context == "development"
    assert target.publish is True
    assert target.branch == "dev/build"


def test_pull_request_publishes_to_pr_scoped_branches(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "42/merge",
        "GITHUB_HEAD_REF": "feature/example",
        "SCAD_PROJECT_PR_NUMBER": "42",
    }
    build = resolve_publication_target(ctx, "build", env)
    verification = resolve_publication_target(ctx, "verification", env)
    assert build.context == "pull_request"
    assert build.publish is True
    assert build.branch == "dev/pr-42/build"
    assert build.source_ref == "feature/example"
    assert verification.branch == "dev/pr-42/verification"


def test_pull_request_number_falls_back_to_merge_ref(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "42/merge",
        "GITHUB_HEAD_REF": "feature/example",
    }
    assert resolve_publication_target(ctx, "build", env).branch == "dev/pr-42/build"


def test_pull_request_without_number_remains_artifact_only(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "pull-request",
        "GITHUB_HEAD_REF": "feature/example",
    }
    target = resolve_publication_target(ctx, "build", env)
    assert target.context == "pull_request"
    assert target.publish is False
    assert target.branch is None


def test_pr_branch_prefix_is_configurable(tmp_path: Path):
    ctx = context(tmp_path)
    ctx.config["publication"]["development"]["pr_branch_prefix"] = "preview/pr"
    assert pull_request_publication_branches(ctx, 7) == (
        "preview/pr-7/build",
        "preview/pr-7/verification",
    )


def test_invalid_explicit_pr_number_is_rejected(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_NAME": "42/merge",
        "SCAD_PROJECT_PR_NUMBER": "not-a-number",
    }
    with pytest.raises(RuntimeError, match="positive integer"):
        resolve_publication_target(ctx, "build", env)


def test_ordinary_version_tag_remains_artifact_only(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "tag",
        "GITHUB_REF_NAME": "v1.2.3",
    }
    target = resolve_publication_target(ctx, "verification", env)
    assert target.context == "tag"
    assert target.publish is False
    assert target.branch is None


def test_coordinated_release_uses_immutable_versioned_branches(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "workflow_call",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
        "SCAD_PROJECT_RELEASE_VERSION": "v1.2.3",
    }

    build = resolve_publication_target(ctx, "build", env)
    verification = resolve_publication_target(ctx, "verification", env)

    assert build.context == "release"
    assert build.branch == "rel/v1.2.3/build"
    assert build.publish is True
    assert build.immutable is True
    assert build.source_ref_type == "tag"
    assert build.source_ref == "v1.2.3"
    assert verification.branch == "rel/v1.2.3/verification"
    assert verification.immutable is True


def test_release_branch_prefix_is_configurable(tmp_path: Path):
    ctx = context(tmp_path)
    ctx.config["publication"]["release"]["branch_prefix"] = "release"
    target = resolve_release_publication_target(ctx, "build", "v2.0.0")
    assert target.branch == "release/v2.0.0/build"


def test_release_version_must_match_configured_pattern(tmp_path: Path):
    ctx = context(tmp_path)
    with pytest.raises(RuntimeError, match="does not match configured tag pattern"):
        resolve_release_publication_target(ctx, "build", "nightly")


def test_legacy_flat_branch_configuration_still_works(tmp_path: Path):
    ctx = ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "publication": {"build_branch": "legacy-build"},
        },
    )
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
    }
    assert resolve_publication_target(ctx, "build", env).branch == "legacy-build"


def test_publication_info_contains_pr_source_provenance(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "42/merge",
        "GITHUB_HEAD_REF": "feature/example",
        "SCAD_PROJECT_PR_NUMBER": "42",
        "GITHUB_REPOSITORY": "brainboxemb/demo",
        "GITHUB_SHA": "abc123",
        "GITHUB_ACTOR": "tester",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "99",
        "SCAD_TOOLCHAIN_IMAGE": "ghcr.io/brainboxemb/scad-toolchain:v0.4.1",
        "SCAD_TOOLCHAIN_VERSION": "v0.4.1",
        "SCAD_PROJECT_WORKFLOW_VERSION": "v0.9.11",
    }
    info = publication_info_text(
        ctx,
        "build",
        env,
        runtime_info="OpenSCAD   : OpenSCAD version test",
        submodule_info="dsg/ext/lib.demo : deadbeef",
    )
    assert "Publication context : pull_request" in info
    assert "Publication branch  : dev/pr-42/build" in info
    assert "Ref                 : feature/example" in info
    assert "Commit              : abc123" in info
    assert "Workflow run        : https://github.com/brainboxemb/demo/actions/runs/99" in info
    assert "SCAD toolchain image: ghcr.io/brainboxemb/scad-toolchain:v0.4.1" in info
    assert "SCAD toolchain ver. : v0.4.1" in info
    assert "tool.scad-project   : v0.9.11" in info
    assert "Git submodules" in info
    assert "dsg/ext/lib.demo : deadbeef" in info
    assert "Runtime components" in info
    assert "OpenSCAD   : OpenSCAD version test" in info


def test_release_provenance_uses_exact_source_sha_override(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "workflow_call",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "release-request/v1.2.3",
        "GITHUB_SHA": "workflow-wrapper-sha",
        "SCAD_PROJECT_RELEASE_VERSION": "v1.2.3",
        "SCAD_PROJECT_SOURCE_SHA": "release-source-sha",
    }

    info = publication_info_text(ctx, "build", env)

    assert "Publication context : release" in info
    assert "Publication branch  : rel/v1.2.3/build" in info
    assert "Ref type            : tag" in info
    assert "Ref                 : v1.2.3" in info
    assert "Commit              : release-source-sha" in info
    assert "workflow-wrapper-sha" not in info


def test_write_publication_info_to_build_root(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF_TYPE", "branch")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    output = write_publication_info(ctx, "build")

    assert output == tmp_path / "bld" / "publication-info.txt"
    assert output.is_file()
    assert "Publication branch  : prod/build" in output.read_text(encoding="utf-8")


def test_publication_info_uses_package_version_outside_reusable_workflow(
    tmp_path: Path,
):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
    }
    info = publication_info_text(ctx, "build", env)
    from scad_project import __version__
    assert f"tool.scad-project   : v{__version__}" in info


def test_cleanup_removes_existing_pr_publication_branches(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    commands: list[list[str]] = []
    existing = {"dev/pr-42/build", "dev/pr-42/verification"}
    monkeypatch.setattr(
        publish_module,
        "_remote_branch_exists",
        lambda _cwd, branch: branch in existing,
    )
    monkeypatch.setattr(
        publish_module,
        "run_checked",
        lambda command, **kwargs: commands.append(command),
    )

    removed = cleanup_pull_request_publication(ctx, 42)

    assert removed == ("dev/pr-42/build", "dev/pr-42/verification")
    assert [command[-2:] for command in commands] == [
        ["--delete", "dev/pr-42/build"],
        ["--delete", "dev/pr-42/verification"],
    ]


def test_cleanup_ignores_missing_pr_publication_branches(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(publish_module, "_remote_branch_exists", lambda *args: False)
    monkeypatch.setattr(
        publish_module,
        "run_checked",
        lambda command, **kwargs: commands.append(command),
    )

    assert cleanup_pull_request_publication(ctx, 42) == ()
    assert commands == []


def test_immutable_snapshot_refuses_existing_release_branch(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("release", encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "brainboxemb/demo")
    monkeypatch.setattr(publish_module, "run_checked", lambda *args, **kwargs: None)
    monkeypatch.setattr(publish_module, "_remote_branch_exists", lambda *args: True)

    with pytest.raises(RuntimeError, match="Immutable release publication branch"):
        publish_module._publish_snapshot(
            source,
            "rel/v1.2.3/build",
            "release",
            immutable=True,
        )


def test_immutable_snapshot_never_force_pushes(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("release", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setenv("GITHUB_REPOSITORY", "brainboxemb/demo")
    monkeypatch.setattr(
        publish_module,
        "run_checked",
        lambda command, **kwargs: commands.append(command),
    )
    monkeypatch.setattr(publish_module, "_remote_branch_exists", lambda *args: False)

    publish_module._publish_snapshot(
        source,
        "rel/v1.2.3/build",
        "release",
        immutable=True,
    )

    push = next(command for command in commands if command[:2] == ["git", "push"])
    assert "--force" not in push
    assert push[-1] == "HEAD:rel/v1.2.3/build"


def test_mutable_snapshot_force_replaces_target(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("production", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setenv("GITHUB_REPOSITORY", "brainboxemb/demo")
    monkeypatch.setattr(
        publish_module,
        "run_checked",
        lambda command, **kwargs: commands.append(command),
    )

    publish_module._publish_snapshot(
        source,
        "prod/build",
        "production",
        immutable=False,
    )

    push = next(command for command in commands if command[:2] == ["git", "push"])
    assert "--force" in push
    assert push[-1] == "HEAD:prod/build"
