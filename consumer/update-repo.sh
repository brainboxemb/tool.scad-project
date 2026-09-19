#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || { echo "Run update-repo.sh from inside a Git repository." >&2; exit 1; }

git_tool="$root/tools/tool.git-project/git-project.sh"
[[ -f "$git_tool" ]] || {
  echo "tool.git-project is not initialized. Run ./bootstrap.sh first." >&2
  exit 1
}

bash "$git_tool" update --repo "$root"

tool_ref="$(
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
          value = substr(value, 2, length(value) - 2)
        }
      }
      return value
    }
    /^dependencies:[[:space:]]*$/ { dependencies = 1; target = 0; next }
    dependencies && /^[^[:space:]]/ { dependencies = 0; target = 0 }
    dependencies && /^  - name:[[:space:]]*/ {
      value = $0
      sub(/^  - name:[[:space:]]*/, "", value)
      target = (unquote(value) == "tool.scad-project")
      next
    }
    dependencies && target && /^    ref:[[:space:]]*/ {
      value = $0
      sub(/^    ref:[[:space:]]*/, "", value)
      print unquote(value)
      exit
    }
  ' "$root/project.yml"
)"

[[ -n "$tool_ref" ]] || {
  echo "project.yml does not declare a tool.scad-project dependency ref." >&2
  exit 1
}

workflow_dir="$root/.github/workflows"
if [[ -d "$workflow_dir" ]]; then
  while IFS= read -r -d '' path; do
    tmp="${path}.tmp.$$"
    sed -E \
      "s#(brainboxemb/tool\\.scad-project/\\.github/workflows/(project-build|project-verify|project-production|project-release)\\.yml)@[^[:space:]\\\"\']+#\\1@${tool_ref}#g" \
      "$path" > "$tmp"
    if ! cmp -s "$path" "$tmp"; then
      mv "$tmp" "$path"
      relative="${path#"$root/"}"
      echo "Updated SCAD workflow ref: $relative -> $tool_ref"
    else
      rm -f "$tmp"
    fi
  done < <(find "$workflow_dir" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)
fi

echo "Repository dependency update complete."
