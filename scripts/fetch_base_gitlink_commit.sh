#!/usr/bin/env bash
set -euo pipefail

base_sha="${1:-}"
submodule_path="${2:-tools/tool.scad-project}"

if [[ ! "$base_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: base commit must be an exact 40-character SHA" >&2
  exit 2
fi

if [[ "$base_sha" == "0000000000000000000000000000000000000000" ]]; then
  echo "No concrete comparison base; no base gitlink object to fetch."
  exit 0
fi

root="$(git rev-parse --show-toplevel)"
entry="$(git -C "$root" ls-tree "$base_sha" -- "$submodule_path" || true)"

if [[ -z "$entry" ]]; then
  echo "Base revision does not contain gitlink $submodule_path; nothing to fetch."
  exit 0
fi

read -r mode type gitlink_sha path <<< "$entry"
if [[ "$mode" != "160000" || "$type" != "commit" || "$path" != "$submodule_path" || ! "$gitlink_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: unexpected base tree entry for $submodule_path: $entry" >&2
  exit 1
fi

if [[ ! -d "$root/$submodule_path/.git" && ! -f "$root/$submodule_path/.git" ]]; then
  echo "ERROR: submodule is not initialized: $submodule_path" >&2
  exit 1
fi

if git -C "$root/$submodule_path" cat-file -e "${gitlink_sha}^{commit}" 2>/dev/null; then
  echo "Base gitlink commit already present: $submodule_path @ $gitlink_sha"
  exit 0
fi

echo "Fetching exact base gitlink commit: $submodule_path @ $gitlink_sha"
git -C "$root/$submodule_path" fetch --no-tags --depth=1 origin "$gitlink_sha"
git -C "$root/$submodule_path" cat-file -e "${gitlink_sha}^{commit}"
