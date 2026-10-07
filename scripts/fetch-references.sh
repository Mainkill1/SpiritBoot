#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.reference}"
UPDATE="${2:-}"
mkdir -p "$ROOT"

REPOS=$(cat <<'EOF'
roswell|main|0|https://github.com/mborgerson/roswell.git
fancy-mouse|master|0|https://github.com/SnowyMouse/fancy-mouse-boot-rom.git
xemu-fork|main|0|https://github.com/Mainkill1/xemu.git
xemu|master|0|https://github.com/xemu-project/xemu.git
kernel-tests|master|0|https://github.com/Cxbx-Reloaded/xbox_kernel_test_suite.git
cxbx-reloaded|master|1|https://github.com/Cxbx-Reloaded/Cxbx-Reloaded.git
xb-symbol-database|master|0|https://github.com/Cxbx-Reloaded/XbSymbolDatabase.git
nxdk|master|1|https://github.com/XboxDev/nxdk.git
cromwell|master|0|https://github.com/XboxDev/cromwell.git
xboxpy|master|0|https://github.com/XboxDev/xboxpy.git
xbox-linux|master|0|https://github.com/XboxDev/xbox-linux.git
EOF
)

printf 'id\tbranch\tcommit\tremote\n' > "$ROOT/.versions.tsv"

while IFS='|' read -r name branch recursive url; do
  path="$ROOT/$name"
  if [[ ! -d "$path/.git" ]]; then
    echo "[clone]  $name"
    args=(clone --branch "$branch")
    [[ "$recursive" == "1" ]] && args+=(--recurse-submodules)
    git "${args[@]}" "$url" "$path"
  elif [[ "$UPDATE" == "--update" ]]; then
    echo "[update] $name"
    git -C "$path" fetch --all --prune
    git -C "$path" checkout "$branch"
    git -C "$path" pull --ff-only
    [[ "$recursive" == "1" ]] && git -C "$path" submodule update --init --recursive
  else
    echo "[keep]   $name"
  fi

  commit="$(git -C "$path" rev-parse HEAD)"
  remote="$(git -C "$path" remote get-url origin)"
  printf '%s\t%s\t%s\t%s\n' "$name" "$branch" "$commit" "$remote" >> "$ROOT/.versions.tsv"
done <<< "$REPOS"

echo "Exact revisions written to $ROOT/.versions.tsv"
