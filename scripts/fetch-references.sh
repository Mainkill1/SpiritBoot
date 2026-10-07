#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.reference}"
mkdir -p "$ROOT"

clone_or_update() {
    local name="$1"
    local url="$2"
    local recursive="${3:-0}"
    local path="$ROOT/$name"

    if [[ -d "$path/.git" ]]; then
        echo "[update] $name"
        git -C "$path" pull --ff-only
        if [[ "$recursive" == "1" ]]; then
            git -C "$path" submodule update --init --recursive --depth 1
        fi
        return
    fi

    echo "[clone]  $name"
    if [[ "$recursive" == "1" ]]; then
        git clone --depth 1 --recurse-submodules --shallow-submodules "$url" "$path"
    else
        git clone --depth 1 "$url" "$path"
    fi
}

clone_or_update cromwell      https://github.com/XboxDev/cromwell.git
clone_or_update xemu          https://github.com/xemu-project/xemu.git
clone_or_update cxbx-reloaded https://github.com/Cxbx-Reloaded/Cxbx-Reloaded.git
clone_or_update nxdk          https://github.com/XboxDev/nxdk.git 1
clone_or_update xboxpy        https://github.com/XboxDev/xboxpy.git
clone_or_update xbox-linux    https://github.com/XboxDev/xbox-linux.git

echo
echo "Reference repositories are available under: $ROOT"
echo "They are research inputs, not automatically part of the SpiritBoot build."
