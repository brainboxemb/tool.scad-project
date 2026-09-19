"""Load and validate the configuration-driven SCAD project context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectContext:
    root: Path
    config_file: Path
    config: dict[str, Any]
    repository_config: dict[str, Any] | None = None

    def path(self, value: str) -> Path:
        return (self.root / value).resolve()


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "project.yml").is_file():
            return candidate
    raise ConfigError("No project.yml found in current directory or its parents.")


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain a YAML mapping at the root.")
    return data


def _scad_profile_file(root: Path, repository: dict[str, Any]) -> Path | None:
    """Return the configured SCAD profile, or None for legacy combined config."""

    if "profiles" not in repository:
        return None

    profiles = repository.get("profiles")
    if not isinstance(profiles, list):
        raise ConfigError("project.yml profiles must be a list.")

    matches = [
        item for item in profiles
        if isinstance(item, dict) and str(item.get("type", "")).strip() == "scad"
    ]
    if not matches:
        raise ConfigError("project.yml does not declare a SCAD profile (type: scad).")
    if len(matches) != 1:
        raise ConfigError("project.yml must declare exactly one SCAD profile.")

    value = matches[0].get("config")
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("The SCAD profile requires a non-empty config path.")

    profile = (root / value).resolve()
    try:
        profile.relative_to(root.resolve())
    except ValueError as exc:
        raise ConfigError("The SCAD profile config path must stay inside the project.") from exc
    if not profile.is_file():
        raise ConfigError(f"SCAD profile config does not exist: {value}")
    return profile


def _repository_dependencies(repository: dict[str, Any]) -> list[dict[str, Any]]:
    raw = repository.get("dependencies", []) or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _compose_scad_config(
    repository: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Adapt generic repository declarations to the existing SCAD runtime model.

    `tool.git-project` owns dependency policy.  The SCAD layer consumes only the
    fields it needs: the project name, the checked-out SCAD tool expectation and
    external CAD locations.  SCAD-only external metadata such as `required_file`
    may stay in the profile and is merged by dependency name.
    """

    result = dict(profile)
    if "project" in repository:
        result["project"] = repository["project"]

    dependencies = _repository_dependencies(repository)
    tool = next(
        (item for item in dependencies if item.get("name") == "tool.scad-project"),
        None,
    )
    if tool is not None:
        result["tooling"] = {
            "tool_scad_project": {
                "type": tool.get("type", "git-submodule"),
                "url": tool.get(
                    "url",
                    "https://github.com/brainboxemb/tool.scad-project.git",
                ),
                "path": tool.get("path", "tools/tool.scad-project"),
                "ref": str(tool.get("ref", "")).strip(),
            }
        }

    generic_externals = [
        item for item in dependencies if str(item.get("role", "")).strip() == "external"
    ]
    if generic_externals:
        profile_externals = profile.get("externals", []) or []
        if not isinstance(profile_externals, list):
            raise ConfigError("project.scad.yml externals must be a list when present.")

        metadata: dict[str, dict[str, Any]] = {}
        for item in profile_externals:
            if not isinstance(item, dict) or not item.get("name"):
                raise ConfigError(
                    "project.scad.yml externals entries require a dependency name."
                )
            metadata[str(item["name"])] = dict(item)

        generic_names = {str(item.get("name", "")) for item in generic_externals}
        unknown = sorted(set(metadata) - generic_names)
        if unknown:
            raise ConfigError(
                "SCAD external metadata has no matching generic dependency: "
                + ", ".join(unknown)
            )

        externals: list[dict[str, Any]] = []
        for dependency in generic_externals:
            name = str(dependency.get("name", ""))
            item = dict(metadata.get(name, {}))
            item.update(
                {
                    "name": name,
                    "type": dependency.get("type", "git-submodule"),
                    "url": dependency.get("url", ""),
                    "path": dependency.get("path", ""),
                    "ref": str(dependency.get("ref", "")).strip(),
                }
            )
            externals.append(item)
        result["externals"] = externals

    return result


def load_context(start: Path | None = None) -> ProjectContext:
    root = find_project_root(start)
    project_file = root / "project.yml"
    repository = _load_mapping(project_file)
    profile_file = _scad_profile_file(root, repository)

    # Compatibility path for current consumers while Step 0.5 rolls out.  Once
    # no supported consumer uses the combined schema this can be removed in a
    # later cleanup/release step.
    if profile_file is None:
        return ProjectContext(root, project_file, repository)

    profile = _load_mapping(profile_file)
    config = _compose_scad_config(repository, profile)
    return ProjectContext(
        root,
        profile_file,
        config,
        repository_config=repository,
    )


def validate_config(context: ProjectContext) -> list[str]:
    errors: list[str] = []
    c = context.config

    if not isinstance(c.get("project"), dict):
        errors.append("Missing mapping: project")
    elif not c["project"].get("name"):
        errors.append("Missing value: project.name")

    if not isinstance(c.get("paths"), dict):
        errors.append("Missing mapping: paths")
    else:
        paths = c["paths"]
        if not paths.get("build_root"):
            errors.append("Missing value: paths.build_root")

        for key in ("render_root", "export_root"):
            value = paths.get(key)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                errors.append(f"paths.{key} must be a non-empty path string")

        render_roots = paths.get("render_roots")
        if render_roots is not None:
            if not isinstance(render_roots, list) or not render_roots:
                errors.append("paths.render_roots must be a non-empty list")
            elif not all(
                isinstance(item, str) and item.strip()
                for item in render_roots
            ):
                errors.append("paths.render_roots must contain path strings")

        design_root = paths.get("design_root")
        design_roots = paths.get("design_roots")
        if not design_root and not design_roots:
            errors.append("Missing value: paths.design_root or paths.design_roots")
        if design_roots is not None:
            if not isinstance(design_roots, list) or not design_roots:
                errors.append("paths.design_roots must be a non-empty list")
            elif not all(isinstance(item, str) and item.strip() for item in design_roots):
                errors.append("paths.design_roots must contain path strings")

    externals = c.get("externals")
    if externals is None:
        externals = c.get("libraries", [])

    if not isinstance(externals, list):
        errors.append("externals must be a list")
    else:
        for index, external in enumerate(externals):
            if not isinstance(external, dict):
                errors.append(f"externals[{index}] must be a mapping")
                continue
            for key in ("name", "path"):
                if not external.get(key):
                    errors.append(f"externals[{index}].{key} is required")
            if not external.get("url"):
                errors.append(f"externals[{index}].url is required")

    tooling = c.get("tooling")
    if tooling is not None:
        if not isinstance(tooling, dict):
            errors.append("tooling must be a mapping")
        else:
            modern = tooling.get("tool_scad_project")
            legacy = tooling.get("tool_scad_project_version")
            if modern is None and legacy is None:
                errors.append(
                    "tooling requires tool_scad_project or "
                    "tool_scad_project_version"
                )
            elif modern is not None:
                if not isinstance(modern, dict):
                    errors.append("tooling.tool_scad_project must be a mapping")
                elif not modern.get("ref"):
                    errors.append("tooling.tool_scad_project.ref is required")

    rendering = c.get("rendering")
    if rendering is not None:
        if not isinstance(rendering, dict):
            errors.append("rendering must be a mapping")
        else:
            watermark = rendering.get("watermark")
            if watermark is not None:
                if not isinstance(watermark, dict):
                    errors.append("rendering.watermark must be a mapping")
                else:
                    text = watermark.get("text")
                    if text is None:
                        errors.append("rendering.watermark.text is required")
                    elif not isinstance(text, str) or not text.strip():
                        errors.append(
                            "rendering.watermark.text must be a non-empty string"
                        )

    verification = c.get("verification")
    if verification is not None:
        if not isinstance(verification, dict):
            errors.append("verification must be a mapping")
        else:
            commands = verification.get("commands", [])
            if not isinstance(commands, list):
                errors.append("verification.commands must be a list")
            else:
                for index, command in enumerate(commands):
                    if not isinstance(command, list) or not command:
                        errors.append(
                            f"verification.commands[{index}] must be a non-empty argv list"
                        )
            output_root = verification.get("output_root")
            if output_root is not None and not isinstance(output_root, str):
                errors.append("verification.output_root must be a path string")

    drawing = c.get("drawing")
    drawing_outputs: list[str] = []
    if drawing is not None:
        if not isinstance(drawing, dict):
            errors.append("drawing must be a mapping")
        else:
            command = drawing.get("command")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(item, str) and item.strip() for item in command)
            ):
                errors.append("drawing.command must be a non-empty argv list")

            inputs = drawing.get("inputs")
            if (
                not isinstance(inputs, list)
                or not inputs
                or not all(isinstance(item, str) and item.strip() for item in inputs)
            ):
                errors.append("drawing.inputs must be a non-empty list of path strings")

            outputs = drawing.get("outputs")
            if (
                not isinstance(outputs, list)
                or not outputs
                or not all(isinstance(item, str) and item.strip() for item in outputs)
            ):
                errors.append("drawing.outputs must be a non-empty list of path strings")
            else:
                drawing_outputs = [str(item) for item in outputs]
                if len(set(drawing_outputs)) != len(drawing_outputs):
                    errors.append("drawing.outputs must not contain duplicates")
                if Path(drawing_outputs[0]).suffix.lower() != ".svg":
                    errors.append(
                        "drawing.outputs[0] must be the canonical .svg drawing"
                    )
                for output in drawing_outputs:
                    if Path(output).suffix.lower() not in {".svg", ".png", ".pdf"}:
                        errors.append(
                            f"Unsupported drawing output extension: {output}"
                        )

                paths = c.get("paths", {}) or {}
                build_root = paths.get("build_root") if isinstance(paths, dict) else None
                if isinstance(build_root, str) and build_root.strip():
                    build_path = Path(build_root)
                    for output in drawing_outputs:
                        output_path = Path(output)
                        if output_path.is_absolute():
                            errors.append(
                                f"drawing output must stay under paths.build_root: {output}"
                            )
                            continue
                        try:
                            output_path.relative_to(build_path)
                        except ValueError:
                            errors.append(
                                f"drawing output must stay under paths.build_root: {output}"
                            )

    publication = c.get("publication")
    if publication is not None:
        if not isinstance(publication, dict):
            errors.append("publication must be a mapping")
        else:
            for section_name in ("production", "development", "tags"):
                section = publication.get(section_name)
                if section is not None and not isinstance(section, dict):
                    errors.append(f"publication.{section_name} must be a mapping")

            production = publication.get("production", {}) or {}
            development = publication.get("development", {}) or {}
            tags = publication.get("tags", {}) or {}

            if isinstance(production, dict):
                source_branch = production.get("source_branch")
                if source_branch is not None and not isinstance(source_branch, str):
                    errors.append("publication.production.source_branch must be a string")
                for key in ("build_branch", "verification_branch"):
                    value = production.get(key)
                    if value is not None and not isinstance(value, str):
                        errors.append(f"publication.production.{key} must be a string")

            if isinstance(development, dict):
                for key in ("build_branch", "verification_branch"):
                    value = development.get(key)
                    if value is not None and not isinstance(value, str):
                        errors.append(f"publication.development.{key} must be a string")

            if isinstance(tags, dict):
                pattern = tags.get("pattern")
                if pattern is not None and not isinstance(pattern, str):
                    errors.append("publication.tags.pattern must be a string")

            for key in ("build_branch", "verification_branch"):
                value = publication.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(f"publication.{key} must be a string")

    seen_names: set[str] = set()
    seen_outputs: set[str] = set()
    for index, build in enumerate(c.get("builds", []) or []):
        if not isinstance(build, dict):
            errors.append(f"builds[{index}] must be a mapping")
            continue
        for key in ("name", "source", "output"):
            if not build.get(key):
                errors.append(f"builds[{index}].{key} is required")

        name = build.get("name")
        output = build.get("output")
        if name:
            if name in seen_names:
                errors.append(f"Duplicate build name: {name}")
            seen_names.add(name)
        if output:
            if output in seen_outputs:
                errors.append(f"Duplicate build output: {output}")
            seen_outputs.add(output)
            if Path(output).suffix.lower() not in {".png", ".stl", ".svg"}:
                errors.append(f"Unsupported build output extension: {output}")

    for output in drawing_outputs:
        if output in seen_outputs:
            errors.append(f"Duplicate build/drawing output: {output}")

    return errors
