"""Migration-005 CI plan and capability/configuration consistency.

Checks:
- runtime/profile and SCons transport follow project.scad.yml intent;
- inherited Moon capabilities must agree with configured SCAD capabilities;
- capability selection is read from project-level moon.yml, matching Moon 2.5.4;
- non-standard output roots require explicit local Moon output overrides;
- precise and conservative Moon impact results resolve to publication-safe materialization scopes.

Testing approach:
- create small temporary consumer repositories with real project/Moon YAML;
- keep .moon/workspace.yml limited to valid workspace-level configuration;
- load them through the production configuration loader and assert the resulting plans/errors.
"""

from pathlib import Path

import pytest

from scad_project.ci_policy import (
    CiPolicyError,
    build_ci_plan,
    resolve_execution_plan,
)
from scad_project.config import load_context


def _write_repository(
    root: Path,
    *,
    profile: str,
    capabilities: list[str],
    local_tasks: str = "tasks: {}\n",
) -> None:
    (root / ".moon" / "tasks").mkdir(parents=True)
    (root / "project.yml").write_text(
        """schema_version: 1
project:
  name: demo
profiles:
  - type: scad
    config: project.scad.yml
""",
        encoding="utf-8",
    )
    (root / "project.scad.yml").write_text(profile, encoding="utf-8")
    include = "\n".join(f"      - {value}" for value in capabilities)
    (root / ".moon" / "workspace.yml").write_text(
        """projects:
  consumer: '.'
""",
        encoding="utf-8",
    )
    (root / ".moon" / "tasks" / "scad.yml").write_text(
        "extends: '../../tools/tool.scad-project/moon/tasks/scad.yml'\n",
        encoding="utf-8",
    )
    (root / "moon.yml").write_text(
        f"""workspace:
  inheritedTasks:
    include:
{include}
{local_tasks}""",
        encoding="utf-8",
    )


def _hub_plan(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
  render_root: openscad/render
build_engine:
  engine: scons
openscad: {}
verification:
  commands:
    - [bash, scripts/verify.sh]
  output_root: vrf/out
""",
        capabilities=["scad.docs", "scad.build", "scad.verify"],
    )
    return build_ci_plan(load_context(tmp_path))


def test_dual_runtime_direct_project_plan(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
openscad: {}
pythonscad:
  common_flags: [--trust-python]
verification:
  commands:
    - [bash, scripts/verify.sh]
  output_root: vrf/out
""",
        capabilities=["scad.docs", "scad.verify"],
    )

    plan = build_ci_plan(load_context(tmp_path))

    assert plan.capabilities == ("scad.docs", "scad.verify")
    assert plan.runtime_profile == "full"
    assert plan.toolchain_version == "v0.5.3"
    assert plan.runtime_image == "ghcr.io/brainboxemb/scad-toolchain:v0.5.3"
    assert plan.build_engine == "direct"
    assert plan.use_scons_cache is False
    assert plan.use_verification_scons_cache is False


def test_openscad_scons_presentation_project_plan(tmp_path: Path):
    plan = _hub_plan(tmp_path)

    assert plan.runtime_profile == "openscad"
    assert plan.toolchain_version == "v0.5.3"
    assert plan.runtime_image == "ghcr.io/brainboxemb/scad-toolchain-openscad:v0.5.3"
    assert plan.build_engine == "scons"
    assert plan.use_scons_cache is True
    assert plan.use_verification_scons_cache is False


def test_verification_scons_transport_only_when_verification_targets_exist(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
build_engine:
  engine: scons
openscad: {}
verification:
  render_root: verification/render
  output_root: vrf/out
""",
        capabilities=["scad.docs", "scad.verify"],
    )

    plan = build_ci_plan(load_context(tmp_path))

    assert plan.use_scons_cache is True
    assert plan.use_verification_scons_cache is True


def test_missing_required_capability_is_rejected(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
  render_root: openscad/render
openscad: {}
""",
        capabilities=["scad.docs"],
    )

    with pytest.raises(CiPolicyError, match="missing inherited capability/capabilities: scad.build"):
        build_ci_plan(load_context(tmp_path))


def test_capability_without_matching_config_is_rejected(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
openscad: {}
""",
        capabilities=["scad.docs", "scad.verify"],
    )

    with pytest.raises(CiPolicyError, match="without matching SCAD config: scad.verify"):
        build_ci_plan(load_context(tmp_path))


def test_nonstandard_build_root_requires_local_moon_output_override(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: generated
openscad: {}
""",
        capabilities=["scad.docs"],
    )

    with pytest.raises(CiPolicyError, match="scad.docs.outputs override"):
        build_ci_plan(load_context(tmp_path))


def test_nonstandard_roots_accept_explicit_local_output_overrides(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: generated
openscad: {}
verification:
  commands:
    - [bash, scripts/verify.sh]
  output_root: checks/out
""",
        capabilities=["scad.docs", "scad.verify"],
        local_tasks="""tasks:
  scad.docs:
    outputs:
      - generated/design/**
  scad.verify:
    outputs:
      - checks/out/**
""",
    )

    plan = build_ci_plan(load_context(tmp_path))

    assert plan.build_root == "generated"
    assert plan.verification_root == "checks/out"


def test_inherited_capability_list_is_required_for_new_ci_plan(tmp_path: Path):
    (tmp_path / ".moon").mkdir()
    (tmp_path / "project.yml").write_text(
        """project:
  name: demo
paths:
  design_root: .
  build_root: bld
externals: []
""",
        encoding="utf-8",
    )
    (tmp_path / ".moon" / "workspace.yml").write_text(
        "projects:\n  consumer: '.'\n",
        encoding="utf-8",
    )
    (tmp_path / "moon.yml").write_text("tasks: {}\n", encoding="utf-8")

    with pytest.raises(CiPolicyError, match="workspace.inheritedTasks.include in moon.yml"):
        build_ci_plan(load_context(tmp_path))


def test_workspace_file_is_not_used_for_project_inherited_task_selection(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
openscad: {}
""",
        capabilities=["scad.docs"],
    )
    workspace_text = (tmp_path / ".moon" / "workspace.yml").read_text(encoding="utf-8")

    assert "inheritedTasks" not in workspace_text
    assert build_ci_plan(load_context(tmp_path)).capabilities == ("scad.docs",)


def test_precise_docs_change_hydrates_complete_build_publication_family(tmp_path: Path):
    plan = _hub_plan(tmp_path)

    execution = resolve_execution_plan(
        plan,
        ["consumer:scad.docs"],
        conservative=False,
    )

    assert execution["affected_capabilities"] == ["scad.docs"]
    assert execution["materialization_capabilities"] == ["scad.docs", "scad.build"]
    assert execution["publish_build"] is True
    assert execution["publish_verification"] is False


def test_precise_verification_change_does_not_materialize_build_family(tmp_path: Path):
    plan = _hub_plan(tmp_path)

    execution = resolve_execution_plan(
        plan,
        ["consumer:scad.verify"],
        conservative=False,
    )

    assert execution["affected_capabilities"] == ["scad.verify"]
    assert execution["materialization_capabilities"] == ["scad.verify"]
    assert execution["publish_build"] is False
    assert execution["publish_verification"] is True


def test_conservative_impact_runs_full_safe_scope(tmp_path: Path):
    plan = _hub_plan(tmp_path)

    execution = resolve_execution_plan(plan, [], conservative=True)

    assert execution["impact_mode"] == "conservative"
    assert execution["affected_capabilities"] == [
        "scad.docs",
        "scad.build",
        "scad.verify",
    ]
    assert execution["materialization_capabilities"] == [
        "scad.docs",
        "scad.build",
        "scad.verify",
    ]
    assert execution["run_runtime"] is True
    assert execution["publish_build"] is True
    assert execution["publish_verification"] is True


def test_non_scad_affected_tasks_do_not_start_scad_runtime(tmp_path: Path):
    plan = _hub_plan(tmp_path)

    execution = resolve_execution_plan(
        plan,
        ["consumer:some.other.task"],
        conservative=False,
    )

    assert execution["affected_capabilities"] == []
    assert execution["materialization_capabilities"] == []
    assert execution["run_runtime"] is False


def test_render_roots_select_scad_build_capability(tmp_path: Path):
    _write_repository(
        tmp_path,
        profile="""paths:
  design_root: .
  build_root: bld
  render_roots:
    - openscad/render3d
    - openscad/render2d
openscad: {}
""",
        capabilities=["scad.docs", "scad.build"],
    )

    plan = build_ci_plan(load_context(tmp_path))
    assert plan.capabilities == ("scad.docs", "scad.build")
