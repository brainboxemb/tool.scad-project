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
        for key in ("design_root", "build_root"):
            if not c["paths"].get(key):
                errors.append(f"Missing value: paths.{key}")

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
