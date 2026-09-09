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

    def path(self, value: str) -> Path:
        return (self.root / value).resolve()


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "project.yml").is_file():
            return candidate
    raise ConfigError("No project.yml found in current directory or its parents.")


def load_context(start: Path | None = None) -> ProjectContext:
    root = find_project_root(start)
    config_file = root / "project.yml"
    try:
        data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_file}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("project.yml must contain a YAML mapping at the root.")
    return ProjectContext(root, config_file, data)


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
            if Path(output).suffix.lower() not in {".png", ".stl"}:
                errors.append(f"Unsupported build output extension: {output}")

    return errors
