"""SCAD-owned CI planning for the shared Migration-005 capability lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from .build_engine_config import validate_build_engine_config
from .config import ProjectContext, load_context, validate_config


SCAD_CAPABILITIES = ("scad.docs", "scad.build", "scad.verify")
TOOLCHAIN_VERSION = "v0.5.0"
RUNTIME_IMAGES = {
    "openscad": f"ghcr.io/brainboxemb/scad-toolchain-openscad:{TOOLCHAIN_VERSION}",
    "full": f"ghcr.io/brainboxemb/scad-toolchain:{TOOLCHAIN_VERSION}",
}


class CiPolicyError(RuntimeError):
    """Raised when project intent and the visible Moon capability model disagree."""


@dataclass(frozen=True)
class CiPlan:
    schema_version: int
    capabilities: tuple[str, ...]
    runtime_profile: str
    runtime_image: str
    toolchain_version: str
    build_engine: str
    use_scons_cache: bool
    use_verification_scons_cache: bool
    build_root: str
    verification_root: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["capabilities"] = list(self.capabilities)
        return data


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CiPolicyError(f"Required Moon configuration is missing: {path.relative_to(path.parent.parent) if path.parent.parent in path.parents else path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CiPolicyError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CiPolicyError(f"{path} must contain a YAML mapping at the root")
    return data


def _inherited_scad_capabilities(root: Path) -> tuple[str, ...]:
    workspace_path = root / ".moon" / "workspace.yml"
    workspace_data = _load_yaml_mapping(workspace_path)
    workspace = workspace_data.get("workspace", {}) or {}
    if not isinstance(workspace, dict):
        raise CiPolicyError(".moon/workspace.yml workspace must be a mapping")
    inherited = workspace.get("inheritedTasks", {}) or {}
    if not isinstance(inherited, dict):
        raise CiPolicyError("workspace.inheritedTasks must be a mapping")
    include = inherited.get("include")
    if not isinstance(include, list):
        raise CiPolicyError(
            "Migration-005 consumers must declare workspace.inheritedTasks.include"
        )

    values: list[str] = []
    for raw in include:
        if not isinstance(raw, str) or not raw.strip():
            raise CiPolicyError("workspace.inheritedTasks.include must contain task IDs")
        value = raw.strip()
        if value.startswith("scad.") and value not in SCAD_CAPABILITIES:
            raise CiPolicyError(f"Unsupported inherited SCAD capability: {value}")
        if value in SCAD_CAPABILITIES and value not in values:
            values.append(value)

    return tuple(capability for capability in SCAD_CAPABILITIES if capability in values)


def _local_moon_tasks(root: Path) -> dict[str, Any]:
    data = _load_yaml_mapping(root / "moon.yml")
    tasks = data.get("tasks", {}) or {}
    if not isinstance(tasks, dict):
        raise CiPolicyError("moon.yml tasks must be a mapping")
    return tasks


def _configured_capabilities(context: ProjectContext) -> tuple[str, ...]:
    config = context.config
    paths = config.get("paths", {}) or {}
    values: list[str] = []

    if paths.get("design_root") or paths.get("design_roots"):
        values.append("scad.docs")

    if paths.get("render_root") or paths.get("export_root") or (config.get("builds", []) or []):
        values.append("scad.build")

    verification = config.get("verification", {}) or {}
    if isinstance(verification, dict) and (
        (verification.get("commands", []) or [])
        or verification.get("render_root")
        or verification.get("export_root")
    ):
        values.append("scad.verify")

    return tuple(capability for capability in SCAD_CAPABILITIES if capability in values)


def _task_outputs(tasks: dict[str, Any], task_id: str) -> list[str]:
    raw = tasks.get(task_id, {}) or {}
    if not isinstance(raw, dict):
        raise CiPolicyError(f"moon.yml task override {task_id} must be a mapping")
    outputs = raw.get("outputs", []) or []
    if not isinstance(outputs, list) or not all(isinstance(item, str) for item in outputs):
        raise CiPolicyError(f"moon.yml {task_id}.outputs must be a list of paths")
    return [item.strip() for item in outputs if item.strip()]


def _has_output_under(outputs: list[str], root: str) -> bool:
    normalized = root.rstrip("/")
    return any(output == normalized or output.startswith(normalized + "/") for output in outputs)


def _validate_output_overrides(
    context: ProjectContext,
    capabilities: tuple[str, ...],
    local_tasks: dict[str, Any],
) -> None:
    paths = context.config.get("paths", {}) or {}
    build_root = str(paths.get("build_root", "bld")).rstrip("/")
    if build_root != "bld":
        for capability in ("scad.docs", "scad.build"):
            if capability in capabilities and not _has_output_under(
                _task_outputs(local_tasks, capability), build_root
            ):
                raise CiPolicyError(
                    f"Non-standard paths.build_root={build_root!r} requires an explicit "
                    f"{capability}.outputs override in moon.yml"
                )

    verification = context.config.get("verification", {}) or {}
    verification_root = str(verification.get("output_root", "vrf/out")).rstrip("/")
    if "scad.verify" in capabilities and verification_root != "vrf/out":
        if not _has_output_under(
            _task_outputs(local_tasks, "scad.verify"), verification_root
        ):
            raise CiPolicyError(
                f"Non-standard verification.output_root={verification_root!r} requires "
                "an explicit scad.verify.outputs override in moon.yml"
            )


def build_ci_plan(context: ProjectContext) -> CiPlan:
    errors = validate_config(context) + validate_build_engine_config(context)
    if errors:
        raise CiPolicyError("\n".join(errors))

    inherited = _inherited_scad_capabilities(context.root)
    configured = _configured_capabilities(context)
    if inherited != configured:
        missing = [value for value in configured if value not in inherited]
        extra = [value for value in inherited if value not in configured]
        parts: list[str] = []
        if missing:
            parts.append("missing inherited capability/capabilities: " + ", ".join(missing))
        if extra:
            parts.append("capability/capabilities without matching SCAD config: " + ", ".join(extra))
        raise CiPolicyError("Moon capability/configuration mismatch: " + "; ".join(parts))

    local_tasks = _local_moon_tasks(context.root)
    _validate_output_overrides(context, inherited, local_tasks)

    pythonscad = context.config.get("pythonscad")
    if pythonscad is not None and not isinstance(pythonscad, dict):
        raise CiPolicyError("pythonscad must be a mapping when configured")
    runtime_profile = "full" if pythonscad is not None else "openscad"

    build_engine = str(
        (context.config.get("build_engine", {}) or {}).get("engine", "direct")
    ).strip().lower()

    verification = context.config.get("verification", {}) or {}
    verification_targets = bool(
        isinstance(verification, dict)
        and (verification.get("render_root") or verification.get("export_root"))
    )

    build_root = str((context.config.get("paths", {}) or {}).get("build_root", "bld"))
    verification_root = str(
        verification.get("output_root", "vrf/out")
        if isinstance(verification, dict)
        else "vrf/out"
    )

    return CiPlan(
        schema_version=1,
        capabilities=inherited,
        runtime_profile=runtime_profile,
        runtime_image=RUNTIME_IMAGES[runtime_profile],
        toolchain_version=TOOLCHAIN_VERSION,
        build_engine=build_engine,
        use_scons_cache=(
            build_engine == "scons"
            and any(value in inherited for value in ("scad.docs", "scad.build"))
        ),
        use_verification_scons_cache=(
            build_engine == "scons"
            and "scad.verify" in inherited
            and verification_targets
        ),
        build_root=build_root,
        verification_root=verification_root,
    )


def main() -> None:
    try:
        context = load_context()
        plan = build_ci_plan(context)
    except (CiPolicyError, RuntimeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print(json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
