#!/usr/bin/env bash
set -euo pipefail

TOOL_REPOSITORY="https://github.com/brainboxemb/tool.scad-project.git"
TOOL_PATH="tools/tool.scad-project"
SKIP_EXTERNALS=0

if [[ "${1:-}" == "--skip-project-externals" ]]; then
  SKIP_EXTERNALS=1
fi

if [[ ! -d .git ]]; then
  echo "ERROR: run bootstrap.sh from the root of a Git repository." >&2
  exit 1
fi

if ! git config -f .gitmodules --get-regexp 'submodule\..*\.path' 2>/dev/null \
    | awk '{print $2}' | grep -Fxq "$TOOL_PATH"; then
  if [[ -d "$TOOL_PATH" ]] && [[ -n "$(ls -A "$TOOL_PATH" 2>/dev/null)" ]]; then
    echo "ERROR: $TOOL_PATH already contains files." >&2
    exit 1
  fi
  rm -rf "$TOOL_PATH"
  git submodule add "$TOOL_REPOSITORY" "$TOOL_PATH"
fi

git submodule update --init --recursive -- "$TOOL_PATH"

if [[ "$SKIP_EXTERNALS" -eq 0 ]]; then
  bash "$TOOL_PATH/scad-project.sh" externals-init
fi

echo
echo "Bootstrap complete."
echo "Local tool:"
echo "  ./$TOOL_PATH/scad-project.sh <command>"
