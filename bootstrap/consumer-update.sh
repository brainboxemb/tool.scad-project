#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || { echo "Run update-repo.sh from inside a Git repository." >&2; exit 1; }
tool="$root/tools/tool.scad-project/scad-project.sh"
[[ -f "$tool" ]] || { echo "tool.scad-project is not initialized. Run ./bootstrap.sh first." >&2; exit 1; }

bash "$tool" --project "$root" repo-update
