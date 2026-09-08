#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" ]]; then
  echo "ERROR: run update-repo.sh from inside a Git repository." >&2
  exit 1
fi
cd "$repo_root"

[[ -f project.yml ]] || { echo "ERROR: project.yml not found." >&2; exit 1; }

declare -a deps=()

trim() {
  local v="$1"
  v="${v#"${v%%[![:space:]]*}"}"
  v="${v%"${v##*[![:space:]]}"}"
  v="${v%\"}"; v="${v#\"}"
  v="${v%\'}"; v="${v#\'}"
  printf '%s' "$v"
}

flush_dep() {
  if [[ -n "${dep_name:-}" ]]; then
    deps+=("${dep_role}|${dep_name}|${dep_type:-git-submodule}|${dep_url:-}|${dep_path:-}|${dep_ref:-}")
  fi
  dep_name=""; dep_role=""; dep_type=""; dep_url=""; dep_path=""; dep_ref=""
}

section=""; in_tool=0
dep_name=""; dep_role=""; dep_type=""; dep_url=""; dep_path=""; dep_ref=""

while IFS= read -r raw || [[ -n "$raw" ]]; do
  [[ -z "${raw//[[:space:]]/}" ]] && continue
  stripped="${raw#"${raw%%[![:space:]]*}"}"
  [[ "$stripped" == \#* ]] && continue
  indent=$(( ${#raw} - ${#stripped} ))

  if [[ "$indent" -eq 0 ]]; then
    flush_dep
    in_tool=0
    case "$stripped" in
      tooling:) section="tooling" ;;
      externals:) section="externals" ;;
      *) section="" ;;
    esac
    continue
  fi

  if [[ "$section" == "tooling" ]]; then
    if [[ "$indent" -eq 2 && "$stripped" == "tool_scad_project:" ]]; then
      flush_dep
      dep_name="tool.scad-project"; dep_role="tooling"; dep_type="git-submodule"
      dep_url="https://github.com/brainboxemb/tool.scad-project.git"
      dep_path="tools/tool.scad-project"; dep_ref=""; in_tool=1
      continue
    fi

    if [[ "$in_tool" -eq 1 && "$indent" -ge 4 && "$stripped" == *:* ]]; then
      key="${stripped%%:*}"; value="$(trim "${stripped#*:}")"
      case "$key" in
        type) dep_type="$value" ;;
        url) dep_url="$value" ;;
        path) dep_path="$value" ;;
        ref) dep_ref="$value" ;;
      esac
    fi
    continue
  fi

  if [[ "$section" == "externals" ]]; then
    if [[ "$indent" -eq 2 && "$stripped" =~ ^-\ name:\ (.+)$ ]]; then
      flush_dep
      dep_name="$(trim "${BASH_REMATCH[1]}")"; dep_role="external"; dep_type="git-submodule"
      dep_url=""; dep_path=""; dep_ref=""
      continue
    fi

    if [[ -n "$dep_name" && "$indent" -ge 4 && "$stripped" == *:* ]]; then
      key="${stripped%%:*}"; value="$(trim "${stripped#*:}")"
      case "$key" in
        type) dep_type="$value" ;;
        url) dep_url="$value" ;;
        path) dep_path="$value" ;;
        ref) dep_ref="$value" ;;
      esac
    fi
  fi
done < project.yml
flush_dep

[[ "${#deps[@]}" -gt 0 ]] || { echo "ERROR: no versioned dependencies found." >&2; exit 1; }

is_gitlink() {
  git ls-files --stage -- "$1" 2>/dev/null | grep -q '^160000 '
}

ensure_registered() {
  local name="$1" url="$2" path="$3"
  is_gitlink "$path" && return

  mkdir -p "$(dirname "$path")"
  if [[ -d "$path" && -n "$(ls -A "$path" 2>/dev/null)" ]]; then
    git -C "$path" rev-parse --git-dir >/dev/null 2>&1 || {
      echo "ERROR: $path contains non-Git files." >&2; exit 1;
    }
  elif [[ -d "$path" ]]; then
    rmdir "$path"
  fi

  echo "Registering $name: $path"
  git submodule add --force "$url" "$path"
  is_gitlink "$path" || { echo "ERROR: no gitlink created for $path." >&2; exit 1; }
}

latest_tag() {
  local path="$1"
  local best="" best_major=-1 best_minor=-1 best_patch=-1
  while IFS= read -r tag; do
    if [[ "$tag" =~ ^v?([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
      major="${BASH_REMATCH[1]}"; minor="${BASH_REMATCH[2]}"; patch="${BASH_REMATCH[3]}"
      if (( major > best_major ||
            (major == best_major && minor > best_minor) ||
            (major == best_major && minor == best_minor && patch > best_patch) )); then
        best="$tag"; best_major="$major"; best_minor="$minor"; best_patch="$patch"
      fi
    fi
  done < <(git -C "$path" tag --list)

  [[ -n "$best" ]] || { echo "ERROR: no stable semantic-version tags for $path." >&2; exit 1; }
  printf '%s\n' "$best"
}

resolve_ref() {
  local path="$1" ref="$2"
  git -C "$path" fetch --prune --tags origin

  if [[ "$ref" == "latest" ]]; then
    tag="$(latest_tag "$path")"
    printf '%s|%s\n' "$tag" "$tag"
    return
  fi

  if git -C "$path" rev-parse --verify "refs/tags/${ref}^{commit}" >/dev/null 2>&1; then
    printf '%s|%s\n' "$ref" "$ref"; return
  fi

  if git -C "$path" rev-parse --verify "refs/remotes/origin/${ref}^{commit}" >/dev/null 2>&1; then
    printf '%s|%s\n' "origin/$ref" "$ref"; return
  fi

  echo "ERROR: ref '$ref' is neither a tag nor a branch on origin for $path." >&2
  exit 1
}

for row in "${deps[@]}"; do
  IFS='|' read -r role name type url path ref <<< "$row"
  [[ "$type" == "git-submodule" ]] || { echo "ERROR: unsupported type $type." >&2; exit 1; }
  [[ -n "$url" && -n "$path" && -n "$ref" ]] || { echo "ERROR: $name requires url/path/ref." >&2; exit 1; }
  ensure_registered "$name" "$url" "$path"
done

git submodule sync
direct_paths=()
for row in "${deps[@]}"; do
  IFS='|' read -r _role _name _type _url _path _ref <<< "$row"
  direct_paths+=("$_path")
done
git submodule update --init -- "${direct_paths[@]}"

declare -a ordered=()
for row in "${deps[@]}"; do [[ "$row" == tooling\|* ]] || ordered+=("$row"); done
for row in "${deps[@]}"; do [[ "$row" == tooling\|* ]] && ordered+=("$row"); done

declare -a results=()
tool_workflow_ref=""

for row in "${ordered[@]}"; do
  IFS='|' read -r role name type url path ref <<< "$row"

  [[ -z "$(git -C "$path" status --porcelain)" ]] || {
    echo "ERROR: dependency '$name' has local changes: $path" >&2; exit 1;
  }

  old="$(git -C "$path" rev-parse HEAD)"
  resolved="$(resolve_ref "$path" "$ref")"
  checkout_ref="${resolved%%|*}"
  workflow_ref="${resolved#*|}"

  git -C "$path" checkout --detach "$checkout_ref"
  new="$(git -C "$path" rev-parse HEAD)"
  results+=("$name|$path|$ref|$workflow_ref|$old|$new")

  [[ "$role" == "tooling" ]] && tool_workflow_ref="$workflow_ref"
done

if [[ -n "$tool_workflow_ref" && -d .github/workflows ]]; then
  while IFS= read -r -d '' file; do
    before="$(cat "$file")"
    after="$(printf '%s' "$before" | sed -E \
      "s#(brainboxemb/tool\\.scad-project/\\.github/workflows/(project-build|project-verify)\\.yml)@[^[:space:]\"']+#\\1@${tool_workflow_ref}#g")"
    if [[ "$after" != "$before" ]]; then
      printf '%s' "$after" > "$file"
      echo "Updated workflow ref: $file"
    fi
  done < <(find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)
fi

echo
echo "Repository dependency update"
echo "============================"
for row in "${results[@]}"; do
  IFS='|' read -r name path requested resolved old new <<< "$row"
  [[ "$old" == "$new" ]] && state="unchanged" || state="updated"
  echo
  echo "$name: $requested -> $resolved [$state]"
  echo "  old  : $old"
  echo "  new  : $new"
  echo "  path : $path"
done

echo
echo "Changes are intentionally left uncommitted."
echo
git status --short
