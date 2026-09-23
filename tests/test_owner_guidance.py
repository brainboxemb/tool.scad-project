"""Protect tool owner/consumer guidance boundaries.

Checks:
- canonical publication namespace examples remain in consumer-facing README;
- repository AGENTS routes shared workflow to brainboxemb.meta;
- owner AGENTS does not reintroduce archived portfolio authorities or the old
  micro-commit workflow.
"""

from pathlib import Path


def test_consumer_readme_uses_canonical_publication_names():
    text = Path("README.md").read_text(encoding="utf-8")

    for expected in (
        "dev/pr-N/bld",
        "dev/pr-N/vrf",
        "prod/bld",
        "prod/vrf",
        "rel/vX.Y.Z/bld",
        "rel/vX.Y.Z/vrf",
    ):
        assert expected in text

    for legacy in (
        "dev/pr-N/build",
        "dev/pr-N/verification",
        "prod/build",
        "prod/verification",
        "rel/vX.Y.Z/build",
        "rel/vX.Y.Z/verification",
    ):
        assert legacy not in text


def test_owner_agents_routes_to_current_shared_guidance():
    text = Path("AGENTS.md").read_text(encoding="utf-8")

    assert "brainboxemb.meta/AGENTS.md" in text
    assert "README.md" in text
    assert "SCAD consumer repositories do **not** inherit these instructions" in text

    for stale in (
        "meta.scad-projects",
        "tech.scad",
        "make the smallest initial commit",
    ):
        assert stale not in text
