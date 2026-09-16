"""Durable phase timing for the shared SCAD production workflow.

The production workflow records a small number of contiguous orchestration phases.
Generated Build/Verification snapshots receive a family-specific copy with snapshot
preparation appended, while detailed capability timing remains in Moon materialization
evidence.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SCHEMA = "brainboxemb.scad-workflow-timings"
SCHEMA_VERSION = 1


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise RuntimeError("timing timestamp must not be empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"invalid timing timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"timing timestamp must include timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def duration_ms(started_at: str, finished_at: str) -> int:
    delta = _parse_utc(finished_at) - _parse_utc(started_at)
    return max(0, int(delta.total_seconds() * 1000))


def load_timings(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read workflow timing evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"workflow timing evidence must be an object: {path}")
    if payload.get("schema") != SCHEMA or payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"unsupported workflow timing schema: {path}")
    if not isinstance(payload.get("phases"), list):
        raise RuntimeError(f"workflow timing phases must be a list: {path}")
    _parse_utc(str(payload.get("workflow_started_at", "")))
    return payload


def _write_timings(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def transition_phase(
    path: Path,
    *,
    finish: str,
    begin: str | None = None,
    workflow_started_at: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Finish the active phase and optionally start the next phase at one boundary."""

    boundary = now or utc_now()
    _parse_utc(boundary)

    if path.is_file():
        payload = load_timings(path)
    else:
        if not workflow_started_at:
            raise RuntimeError("workflow_started_at is required for the first timing transition")
        _parse_utc(workflow_started_at)
        payload = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "workflow_started_at": workflow_started_at,
            "phases": [],
            "active_phase": {
                "name": finish,
                "started_at": workflow_started_at,
            },
        }

    active = payload.get("active_phase")
    if not isinstance(active, dict) or active.get("name") != finish:
        current = active.get("name") if isinstance(active, dict) else None
        raise RuntimeError(
            f"cannot finish workflow timing phase {finish!r}; active phase is {current!r}"
        )

    started_at = str(active.get("started_at", ""))
    _parse_utc(started_at)
    payload["phases"].append(
        {
            "name": finish,
            "started_at": started_at,
            "finished_at": boundary,
            "duration_ms": duration_ms(started_at, boundary),
        }
    )
    if begin:
        payload["active_phase"] = {"name": begin, "started_at": boundary}
    else:
        payload.pop("active_phase", None)

    _write_timings(path, payload)
    return payload


def begin_phase(path: Path, *, phase: str, now: str | None = None) -> dict[str, Any]:
    """Start a later phase after the previous phase sequence has been closed."""

    payload = load_timings(path)
    if payload.get("active_phase") is not None:
        raise RuntimeError("cannot begin workflow timing phase while another phase is active")
    started_at = now or utc_now()
    _parse_utc(started_at)
    payload["active_phase"] = {"name": phase, "started_at": started_at}
    _write_timings(path, payload)
    return payload


def snapshot_timings(
    path: Path,
    *,
    publication_family: str,
    snapshot_started_at: str,
    snapshot_finished_at: str,
    snapshot_duration_ms: int | None = None,
) -> dict[str, Any]:
    """Return immutable timing evidence for one prepared publication snapshot."""

    payload = deepcopy(load_timings(path))
    if payload.get("active_phase") is not None:
        raise RuntimeError("cannot snapshot workflow timings while a phase is active")
    if publication_family not in {"build", "verification"}:
        raise RuntimeError(f"unsupported publication family: {publication_family}")

    _parse_utc(snapshot_started_at)
    _parse_utc(snapshot_finished_at)
    measured = duration_ms(snapshot_started_at, snapshot_finished_at)
    if snapshot_duration_ms is not None:
        measured = max(0, int(snapshot_duration_ms))

    payload["phases"].append(
        {
            "name": "snapshot_preparation",
            "started_at": snapshot_started_at,
            "finished_at": snapshot_finished_at,
            "duration_ms": measured,
        }
    )
    payload["publication_family"] = publication_family
    payload["snapshot_ready_at"] = snapshot_finished_at
    payload["total_to_snapshot_ms"] = duration_ms(
        str(payload["workflow_started_at"]),
        snapshot_finished_at,
    )
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    transition = subparsers.add_parser("transition")
    transition.add_argument("--file", required=True, type=Path)
    transition.add_argument("--finish", required=True)
    transition.add_argument("--begin")
    transition.add_argument("--workflow-started-at")

    begin = subparsers.add_parser("begin")
    begin.add_argument("--file", required=True, type=Path)
    begin.add_argument("--phase", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "transition":
        transition_phase(
            args.file,
            finish=args.finish,
            begin=args.begin,
            workflow_started_at=args.workflow_started_at,
        )
    elif args.command == "begin":
        begin_phase(args.file, phase=args.phase)
    else:  # pragma: no cover - argparse rejects unsupported commands
        raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
