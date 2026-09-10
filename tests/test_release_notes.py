"""Release notes

Checks:
Release notes can extract the requested version from the supported changelog heading
styles, fail when that version is missing, require an exact 40-character source commit,
and include links to the immutable build/verification branches together with checksum
information.

Testing approach:
The tests write small temporary changelog files, call the real changelog/release-note
functions, and inspect the returned Markdown text. No GitHub Release is created; only
the text and provenance rules are tested.
"""

from pathlib import Path

import pytest

from scad_project.config import ProjectContext
from scad_project.release_notes import changelog_release_section, release_notes_text


SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"


def context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        tmp_path,
        tmp_path / "project.yml",
        {
            "project": {"name": "demo"},
            "paths": {"design_root": "dsg", "build_root": "bld"},
            "verification": {"output_root": "vrf/out"},
            "publication": {
                "release": {
                    "branch_prefix": "rel",
                    "tag_pattern": "v*",
                    "changelog": "CHANGELOG.md",
                }
            },
        },
    )


def test_extracts_plain_v_version_heading(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## v0.2.0\n\n### Added\n\n- New thing.\n\n## v0.1.0\n\n- Old thing.\n",
        encoding="utf-8",
    )

    assert changelog_release_section(context(tmp_path), "v0.2.0") == (
        "### Added\n\n- New thing."
    )


def test_extracts_bracketed_version_with_date(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.2.0] - 2026-09-10\n\n### Changed\n\n- Better.\n",
        encoding="utf-8",
    )

    assert changelog_release_section(context(tmp_path), "v0.2.0") == (
        "### Changed\n\n- Better."
    )


def test_missing_release_section_fails(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n- Work in progress.\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="no release section for v0.2.0"):
        changelog_release_section(context(tmp_path), "v0.2.0")


def test_release_notes_include_changelog_and_immutable_browse_links(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## v0.2.0\n\n### Added\n\n- Release feature.\n",
        encoding="utf-8",
    )

    notes = release_notes_text(
        context(tmp_path),
        "v0.2.0",
        SOURCE_SHA,
        repository="brainboxemb/demo",
        server_url="https://github.com",
    )

    assert "### Added\n\n- Release feature." in notes
    assert f"Source commit: `{SOURCE_SHA}`" in notes
    assert "https://github.com/brainboxemb/demo/tree/rel/v0.2.0/build" in notes
    assert "https://github.com/brainboxemb/demo/tree/rel/v0.2.0/verification" in notes
    assert "SHA256SUMS.txt" in notes


def test_release_notes_require_exact_source_sha(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## v0.2.0\n\n- Release feature.\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="exact 40-character"):
        release_notes_text(
            context(tmp_path),
            "v0.2.0",
            "short",
            repository="brainboxemb/demo",
        )
