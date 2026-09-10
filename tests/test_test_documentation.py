"""Test documentation

Checks:
Every `tests/test_*.py` module must explain its purpose with an `Area` title, a
`Checks:` section and a `Testing approach:` section. The generated HTML must remain a
compact overview and must not expose individual pytest test functions, fixtures or
internal testing details.

Testing approach:
The first test reads Python files with the standard-library AST, so it can inspect
module docstrings without importing or executing the test modules. The second test
runs the real documentation generator and inspects its HTML output, including the
number of table rows and the absence of function/fixture names or detailed testing-
method text.
"""

import ast
from pathlib import Path
import subprocess
import sys


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parent


def _module_docstring(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return ast.get_docstring(tree, clean=True)


def test_every_test_module_has_structured_explanation():
    missing: list[str] = []
    malformed: list[str] = []

    for path in sorted(TEST_ROOT.glob("test_*.py")):
        docstring = _module_docstring(path)
        if not docstring:
            missing.append(path.name)
            continue
        if "\n\nChecks:\n" not in docstring or "\n\nTesting approach:\n" not in docstring:
            malformed.append(path.name)

    assert missing == [], f"Test modules without a module docstring: {missing}"
    assert malformed == [], (
        "Test module docstrings must contain 'Checks:' and 'Testing approach:' "
        f"sections: {malformed}"
    )


def test_generated_reference_is_overview_not_api_documentation(tmp_path: Path):
    output = tmp_path / "index.html"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_test_reference.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )

    text = output.read_text(encoding="utf-8")
    module_count = len(list(TEST_ROOT.glob("test_*.py")))

    assert "<th>Area</th><th>What is checked</th><th>Source</th>" in text
    assert "test_png_build_without_watermark_uses_direct_output" not in text
    assert "tmp_path" not in text
    assert "monkeypatch" not in text
    assert "temporarily replacing the function" not in text
    assert text.count("<tr>") - 1 == module_count
