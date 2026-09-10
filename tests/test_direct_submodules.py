"""Non-recursive submodule checkout

Checks:
Normal bootstrap, repository update, dependency setup and reusable Build/Verify
workflows must initialize only the submodules they explicitly manage. Recursive
submodule checkout is forbidden because it can unexpectedly pull nested repositories
that are not part of the declared project dependency policy.

Testing approach:
The test reads the relevant scripts, Python modules and workflow files and searches for
the known recursive-submodule command-line flags. It fails if any of those flags are
introduced.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_normal_repository_scripts_do_not_use_recursive_submodules():
    files = [
        ROOT / "bootstrap" / "bootstrap.ps1",
        ROOT / "bootstrap" / "bootstrap.sh",
        ROOT / "update-repo.ps1",
        ROOT / "update-repo.sh",
        ROOT / "src" / "scad_project" / "dependencies.py",
        ROOT / "src" / "scad_project" / "externals.py",
        ROOT / ".github" / "workflows" / "project-build.yml",
        ROOT / ".github" / "workflows" / "project-verify.yml",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "submodules: recursive" not in text, path
        assert "submodule update --init --recursive" not in text, path
        assert '"--recursive"' not in text, path
