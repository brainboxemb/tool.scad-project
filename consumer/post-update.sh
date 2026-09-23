#!/usr/bin/env bash
set -euo pipefail

repo_root=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) repo_root="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v git >/dev/null 2>&1 || { echo "Git was not found in PATH." >&2; exit 1; }

if [[ -n "$repo_root" ]]; then
  repo_root="$(git -C "$repo_root" rev-parse --show-toplevel)"
else
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi
[[ -n "$repo_root" ]] || { echo "Unable to resolve consumer repository root." >&2; exit 1; }

scad_tool_ref="$(
  awk '
    function trim(value) {
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      return value
    }
    function unquote(value) {
      value = trim(value)
      if (length(value) >= 2) {
        first = substr(value, 1, 1)
        last = substr(value, length(value), 1)
        if ((first == "\"" && last == "\"") || (first == "\047" && last == "\047")) {
          return substr(value, 2, length(value) - 2)
        }
      }
      return value
    }
    /^[^[:space:]]/ {
      in_dependencies = ($0 ~ /^dependencies:[[:space:]]*$/)
      if (!in_dependencies) in_scad_tool = 0
      next
    }
    in_dependencies && /^  - name:[[:space:]]*/ {
      value = $0
      sub(/^  - name:[[:space:]]*/, "", value)
      in_scad_tool = (unquote(value) == "tool.scad-project")
      next
    }
    in_dependencies && in_scad_tool && /^    ref:[[:space:]]*/ {
      value = $0
      sub(/^    ref:[[:space:]]*/, "", value)
      print unquote(value)
      exit
    }
  ' "$repo_root/project.yml"
)"

[[ -n "$scad_tool_ref" ]] || {
  echo "project.yml does not declare a ref for dependency 'tool.scad-project'." >&2
  exit 1
}

workflow_root="$repo_root/.github/workflows"
if [[ -d "$workflow_root" ]]; then
  for workflow in "$workflow_root"/*.yml "$workflow_root"/*.yaml; do
    [[ -f "$workflow" ]] || continue
    tmp="$(mktemp)"
    sed -E       "s#(brainboxemb/tool\.scad-project/\.github/workflows/(reusable-build|reusable-verify|reusable-ci|reusable-release)\.yml)@[^[:space:]\"']+#\1@${scad_tool_ref}#g"       "$workflow" > "$tmp"
    if ! cmp -s "$workflow" "$tmp"; then
      cat "$tmp" > "$workflow"
      rel="${workflow#"$repo_root"/}"
      echo "Updated SCAD workflow ref: $rel -> $scad_tool_ref"
    fi
    rm -f "$tmp"
  done
fi

echo "SCAD post-update synchronization complete."
