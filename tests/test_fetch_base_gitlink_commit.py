"""Exact base gitlink acquisition for shallow Migration-005 preflight.

Checks:
The SCAD preflight helper reads the tool gitlink from the exact parent base
revision and fetches only that commit into a shallow current submodule checkout
when the object is missing. A missing/conservative base remains a no-op.

Testing approach:
Create local Git repositories for a two-revision tool and a consumer whose base
points at tool revision A while head points at B. Clone the consumer and its
submodule shallowly at head, fetch only the exact parent base commit, prove A is
absent from the submodule, run the helper, and then prove exactly the required
base object became available.
"""

from __future__ import annotations

from pathlib import Path
import subprocess


SCRIPT = Path("scripts/fetch_base_gitlink_commit.sh").resolve()


def _run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _git(cwd: Path, *args: str) -> str:
    return _run("git", *args, cwd=cwd).stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.name", "test")
    _git(path, "config", "user.email", "test@example.invalid")


def _commit_file(repo: Path, text: str, message: str) -> str:
    (repo / "value.txt").write_text(text, encoding="utf-8")
    _git(repo, "add", "value.txt")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_fetches_only_missing_base_gitlink_commit(tmp_path: Path):
    tool = tmp_path / "tool"
    _init_repo(tool)
    tool_a = _commit_file(tool, "A\n", "A")
    tool_b = _commit_file(tool, "B\n", "B")

    consumer = tmp_path / "consumer"
    _init_repo(consumer)
    tool_url = tool.as_uri()
    _git(
        consumer,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        tool_url,
        "tools/tool.scad-project",
    )
    _git(consumer / "tools/tool.scad-project", "checkout", "-q", tool_a)
    _git(consumer, "add", ".gitmodules", "tools/tool.scad-project")
    _git(consumer, "commit", "-q", "-m", "base")
    base_sha = _git(consumer, "rev-parse", "HEAD")

    _git(consumer / "tools/tool.scad-project", "checkout", "-q", tool_b)
    _git(consumer, "add", "tools/tool.scad-project")
    _git(consumer, "commit", "-q", "-m", "head")

    shallow = tmp_path / "shallow"
    _run(
        "git",
        "clone",
        "-q",
        "--depth=1",
        consumer.as_uri(),
        str(shallow),
        cwd=tmp_path,
    )
    _git(
        shallow,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "--depth=1",
        "--",
        "tools/tool.scad-project",
    )
    _git(shallow, "fetch", "--no-tags", "--depth=1", "origin", base_sha)

    before = _run(
        "git",
        "cat-file",
        "-e",
        f"{tool_a}^{{commit}}",
        cwd=shallow / "tools/tool.scad-project",
        check=False,
    )
    assert before.returncode != 0

    result = _run(
        "bash",
        str(SCRIPT),
        base_sha,
        "tools/tool.scad-project",
        cwd=shallow,
    )
    assert f"Fetching exact base gitlink commit: tools/tool.scad-project @ {tool_a}" in result.stdout
    assert _git(shallow / "tools/tool.scad-project", "rev-parse", f"{tool_a}^{{commit}}") == tool_a
    assert _git(shallow / "tools/tool.scad-project", "rev-parse", "HEAD") == tool_b


def test_missing_base_is_a_noop(tmp_path: Path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "head\n", "head")

    result = _run(
        "bash",
        str(SCRIPT),
        "0" * 40,
        cwd=repo,
    )
    assert "No concrete comparison base" in result.stdout
