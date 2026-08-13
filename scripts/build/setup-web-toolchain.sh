#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/build-system/emscripten-version.txt")"
cache_home="${XDG_CACHE_HOME:-${HOME:?HOME is required when XDG_CACHE_HOME is unset}/.cache}"
emsdk_dir="${TERMIN_EMSDK_DIR:-$cache_home/termin/toolchains/emscripten/$version/emsdk}"
version_root="$(dirname "$emsdk_dir")"

if [[ "${1:-}" == "--print-path" ]]; then
    printf '%s\n' "$emsdk_dir"
    exit 0
fi
if (($#)); then
    echo "ERROR: unsupported argument: $1" >&2
    exit 2
fi

if ! command -v flock >/dev/null 2>&1; then
    echo "ERROR: flock is required to manage the shared Emscripten cache safely" >&2
    exit 1
fi

mkdir -p "$version_root"
exec 9>"$version_root/.install.lock"
flock 9

if [[ ! -d "$emsdk_dir/.git" ]]; then
    if [[ -e "$emsdk_dir" ]]; then
        echo "ERROR: incomplete Emscripten cache entry: $emsdk_dir" >&2
        echo "Remove or repair that version directory, then retry." >&2
        exit 1
    fi
    git clone https://github.com/emscripten-core/emsdk.git "$emsdk_dir"
fi

"$emsdk_dir/emsdk" install "$version"
"$emsdk_dir/emsdk" activate "$version"

emcc="$emsdk_dir/upstream/emscripten/emcc"
emcmake="$emsdk_dir/upstream/emscripten/emcmake"
if [[ ! -x "$emcc" || ! -x "$emcmake" ]]; then
    echo "ERROR: Emscripten $version installation is incomplete: $emsdk_dir" >&2
    exit 1
fi

echo "Termin Core Web toolchain ready: Emscripten $version at $emsdk_dir"
