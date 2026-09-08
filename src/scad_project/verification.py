"""Run project-specific functional verification declared in project.yml."""

from __future__ import annotations

from typing import Any

from .config import ProjectContext
from .process import run_checked


def verification_commands(context: ProjectContext) -> list[list[str]]:
    """Return validated argv-style verification commands."""

    verification = context.config.get("verification", {}) or {}
    raw = verification.get("commands", []) or []
    commands: list[list[str]] = []

    for index, command in enumerate(raw):
        if not isinstance(command, list) or not command:
            raise RuntimeError(
                f"verification.commands[{index}] must be a non-empty argv list"
            )
        if not all(isinstance(value, (str, int, float)) for value in command):
            raise RuntimeError(
                f"verification.commands[{index}] values must be scalar strings/numbers"
            )
        commands.append([str(value) for value in command])

    return commands


def run_functional_verification(context: ProjectContext) -> None:
    """Run each configured project verification command in repository order."""

    commands = verification_commands(context)
    if not commands:
        raise RuntimeError("No verification.commands are configured")

    for command in commands:
        run_checked(command, cwd=context.root)
