from __future__ import annotations
from pathlib import Path
import subprocess


def run_checked(args: list[str], *, cwd: Path) -> None:
    print("+", " ".join(args))
    try:
        subprocess.run(args, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed with exit code {exc.returncode}: {' '.join(args)}"
        ) from exc
