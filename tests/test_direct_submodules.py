"""Non-recursive consumer checkout

Checks:
SCAD-owned consumer helpers and reusable Build/Verify workflows must never introduce a
recursive submodule checkout. Generic dependency registration and update belong to
`tool.git-project`, so this repository no longer tests or implements those Git details.

Testing approach:
The test reads only the files still owned by the SCAD project layer and rejects the known
recursive-submodule command-line flags. Generic Git-tool behaviour is tested in its own
repository.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scad_owned_scripts_do_not_use_recursive_submodules():
    files = [
        ROOT / "consumer" / "update-repo.ps1",
        ROOT / "consumer" / "update-repo.sh",
        ROOT / "src" / "scad_project" / "repository.py",
        ROOT / "src" / "scad_project" / "externals.py",
        ROOT / ".github" / "workflows" / "project-build.yml",
        ROOT / ".github" / "workflows" / "project-verify.yml",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "submodules: recursive" not in text, path
        assert "submodule update --init --recursive" not in text, path
        assert '"--recursive"' not in text, path
