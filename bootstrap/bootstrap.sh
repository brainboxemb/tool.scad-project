#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" ]]; then
  echo "ERROR: run bootstrap.sh from inside a Git repository." >&2
  exit 1
fi
cd "$repo_root"

if [[ ! -f .gitmodules ]]; then
  echo "ERROR: .gitmodules is missing." >&2
  exit 1
fi

mapfile -t path_lines < <(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)
if [[ "${#path_lines[@]}" -eq 0 ]]; then
  echo "ERROR: no submodules declared in .gitmodules." >&2
  exit 1
fi

is_gitlink() {
  local path="$1"
  git ls-files --stage -- "$path" 2>/dev/null | grep -q '^160000 '
}

direct_paths=()
for line in "${path_lines[@]}"; do
  key="${line%% *}"
  path="${line#* }"
  name="${key#submodule.}"
  name="${name%.path}"
  url="$(git config -f .gitmodules --get "submodule.${name}.url")"
  direct_paths+=("$path")

  if is_gitlink "$path"; then
    echo "Registered: $path"
    continue
  fi

  echo "Registering missing gitlink: $path"
  parent="$(dirname "$path")"
  [[ "$parent" == "." ]] || mkdir -p "$parent"

  if [[ -d "$path" && -n "$(ls -A "$path" 2>/dev/null)" && ! -e "$path/.git" ]]; then
    echo "ERROR: $path contains non-submodule files." >&2
    exit 1
  fi
  if [[ -d "$path" && -z "$(ls -A "$path" 2>/dev/null)" ]]; then
    rmdir "$path"
  fi

  git submodule add --force "$url" "$path"

  if ! is_gitlink "$path"; then
    echo "ERROR: registration did not create gitlink mode 160000 for $path." >&2
    exit 1
  fi
done

git submodule sync
git submodule update --init -- "${direct_paths[@]}"

for line in "${path_lines[@]}"; do
  path="${line#* }"
  if ! is_gitlink "$path"; then
    echo "ERROR: bootstrap validation failed for $path (not mode 160000)." >&2
    exit 1
  fi
done

echo
echo "Bootstrap complete. All declared submodules have gitlinks."
git submodule status
echo
echo "Review parent repository changes with: git status"
