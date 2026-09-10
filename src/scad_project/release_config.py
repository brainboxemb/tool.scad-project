"""Validation for optional versioned release publication configuration."""

from __future__ import annotations

from .config import ProjectContext


def validate_release_config(context: ProjectContext) -> list[str]:
    """Return configuration errors for publication.release."""

    publication = context.config.get("publication")
    if publication is None or not isinstance(publication, dict):
        return []

    release = publication.get("release")
    if release is None:
        return []
    if not isinstance(release, dict):
        return ["publication.release must be a mapping"]

    errors: list[str] = []
    for key in ("branch_prefix", "tag_pattern", "changelog"):
        value = release.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"publication.release.{key} must be a non-empty string")

    return errors
