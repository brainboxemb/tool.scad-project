#!/usr/bin/env python3
"""Run one SCAD producer action with durable producer timing context."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"design-build", "build", "verify"}:
        raise SystemExit(
            "usage: run_scad_capability.py {design-build|build|verify}"
        )

    tool_root = Path(__file__).resolve().parents[1]
    action = sys.argv[1]
    env = os.environ.copy()
    env["SCAD_PROJECT_PRODUCER_STARTED_AT"] = _utc_now()
    env["SCAD_PROJECT_PRODUCER_STARTED_MONOTONIC_NS"] = str(time.monotonic_ns())

    os.execvpe(
        "bash",
        ["bash", str(tool_root / "scad-project.sh"), action],
        env,
    )


if __name__ == "__main__":
    main()
