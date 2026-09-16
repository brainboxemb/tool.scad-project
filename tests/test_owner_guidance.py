from pathlib import Path


def test_owner_guidance_uses_canonical_publication_names():
    text = Path("AGENTS.md").read_text(encoding="utf-8")

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
