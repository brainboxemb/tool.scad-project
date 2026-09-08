#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tool="$root/tools/tool.scad-project/scad-project.sh"

if [[ ! -f "$tool" ]]; then
  echo "ERROR: tool.scad-project is not initialized. Run ./bootstrap.sh first." >&2
  exit 1
fi

bash "$tool" repo-update
