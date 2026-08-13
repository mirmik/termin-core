#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/build-system/emscripten-version.txt")"
emsdk_dir="${TERMIN_EMSDK_DIR:-$repo_root/build/toolchains/emsdk}"

if [[ ! -d "$emsdk_dir/.git" ]]; then
    mkdir -p "$(dirname "$emsdk_dir")"
    git clone https://github.com/emscripten-core/emsdk.git "$emsdk_dir"
fi

"$emsdk_dir/emsdk" install "$version"
"$emsdk_dir/emsdk" activate "$version"
echo "Termin Core Web toolchain ready: Emscripten $version at $emsdk_dir"
