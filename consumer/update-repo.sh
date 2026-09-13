#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
tool="$root/tools/tool.scad-project/scad-project.sh"
[[ -f "$tool" ]] || {
  echo "tool.scad-project is not initialized. Run ./bootstrap.sh first." >&2
  exit 1
}

bash "$tool" --project "$root" repo-update
