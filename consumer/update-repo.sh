#!/usr/bin/env bash
set -euo pipefail

# Compatibility forwarder only.
# Canonical root update-repo.* launchers are managed by tool.git-project.
mode="${1:-update}"
case "$mode" in
  update|status) ;;
  *) echo "Usage: ./update-repo.sh [update|status]" >&2; exit 2 ;;
esac

command -v git >/dev/null 2>&1 || { echo "Git was not found in PATH." >&2; exit 1; }
root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || { echo "Run update-repo.sh from inside a Git repository." >&2; exit 1; }

git_tool="$root/tools/tool.git-project/git-project.sh"
[[ -f "$git_tool" ]] || {
  echo "tool.git-project is not initialized. Run ./bootstrap.sh first." >&2
  exit 1
}
bash "$git_tool" "$mode" --repo "$root"
[[ "$mode" == "status" ]] && exit 0

hook="$root/tools/tool.scad-project/consumer/post-update.sh"
[[ -f "$hook" ]] || { echo "SCAD post-update hook not found at $hook" >&2; exit 1; }
bash "$hook" --repo "$root"
