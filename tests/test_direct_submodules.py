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
