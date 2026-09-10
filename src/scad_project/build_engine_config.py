"""Validate configuration for the optional build-engine selector."""

from __future__ import annotations

from .config import ProjectContext


def validate_build_engine_config(context: ProjectContext) -> list[str]:
    raw = context.config.get("build_engine")
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["build_engine must be a mapping"]

    engine = raw.get("engine", "direct")
    if not isinstance(engine, str) or engine.strip().lower() not in {"direct", "scons"}:
        return ["build_engine.engine must be 'direct' or 'scons'"]

    return []
