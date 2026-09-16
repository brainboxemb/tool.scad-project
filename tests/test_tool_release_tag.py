"""Tool release-tag contract for cross-repository reusable workflows.

Checks:
The tool release workflow publishes semantic version tags as lightweight refs that
point directly at the already-qualified release commit. It must not create an
annotated tag object, because GitHub cannot compile nested reusable workflows when
a cross-repository workflow caller resolves through such an annotated tag.

Testing approach:
Inspect the owner release workflow source. Cross-repository behavior is qualified
separately with the template.scad-project contract probe and final reference
consumer release before this change is released broadly.
"""

from pathlib import Path


RELEASE = Path(".github/workflows/release.yml")


def test_tool_release_tag_points_directly_to_qualified_commit():
    text = RELEASE.read_text(encoding="utf-8")

    assert "name: Create lightweight release tag" in text
    assert 'git tag "${VERSION}" "${RELEASE_SHA}"' in text
    assert 'git tag -a "${VERSION}"' not in text
    assert 'git push origin "refs/tags/${VERSION}"' in text
