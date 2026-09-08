#!/usr/bin/env bash
set -euo pipefail

TOOL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${TOOL_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m scad_project.cli "$@"
