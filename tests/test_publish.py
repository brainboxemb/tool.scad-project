from pathlib import Path

from scad_project.config import ProjectContext
from scad_project.publish import (
    publication_info_text,
    resolve_publication_target,
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
                "production": {
                    "source_branch": "main",
                    "build_branch": "build",
                    "verification_branch": "verification",
                },
                "development": {
                    "build_branch": "dev/build",
                    "verification_branch": "dev/verification",
                },
                "tags": {"pattern": "v*"},
            },
        },
    )


def test_main_uses_production_branches(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
    }
    assert resolve_publication_target(ctx, "build", env).branch == "build"
    assert (
        resolve_publication_target(ctx, "verification", env).branch
        == "verification"
    )


def test_feature_branch_uses_shared_development_branches(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "feature/example",
    }
    target = resolve_publication_target(ctx, "build", env)
    assert target.context == "development"
    assert target.publish is True
    assert target.branch == "dev/build"


def test_pull_request_is_artifact_only(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "42/merge",
        "GITHUB_HEAD_REF": "feature/example",
    }
    target = resolve_publication_target(ctx, "build", env)
    assert target.context == "pull_request"
    assert target.publish is False
    assert target.branch is None
    assert target.source_ref == "feature/example"


def test_version_tag_is_artifact_only(tmp_path: Path):
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


def test_publication_info_contains_source_provenance(tmp_path: Path):
    ctx = context(tmp_path)
    env = {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "feature/example",
        "GITHUB_REPOSITORY": "brainboxemb/demo",
        "GITHUB_SHA": "abc123",
        "GITHUB_ACTOR": "tester",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "99",
    }
    env.update({
        "SCAD_TOOLCHAIN_IMAGE": "ghcr.io/brainboxemb/scad-toolchain:v0.4.0",
        "SCAD_TOOLCHAIN_VERSION": "v0.4.0",
        "SCAD_PROJECT_WORKFLOW_VERSION": "v0.6.1",
    })
    info = publication_info_text(
        ctx,
        "build",
        env,
        runtime_info="OpenSCAD   : OpenSCAD version test",
    )
    assert "Publication context : development" in info
    assert "Publication branch  : dev/build" in info
    assert "Ref                 : feature/example" in info
    assert "Commit              : abc123" in info
    assert "Workflow run        : https://github.com/brainboxemb/demo/actions/runs/99" in info
    assert "SCAD toolchain image: ghcr.io/brainboxemb/scad-toolchain:v0.4.0" in info
    assert "SCAD toolchain ver. : v0.4.0" in info
    assert "tool.scad-project   : v0.6.1" in info
    assert "Runtime components" in info
    assert "OpenSCAD   : OpenSCAD version test" in info


def test_write_publication_info_to_build_root(tmp_path: Path, monkeypatch):
    ctx = context(tmp_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF_TYPE", "branch")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    output = write_publication_info(ctx, "build")

    assert output == tmp_path / "bld" / "publication-info.txt"
    assert output.is_file()
    assert "Publication branch  : build" in output.read_text(encoding="utf-8")


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
