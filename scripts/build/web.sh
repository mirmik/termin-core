#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/build-system/emscripten-version.txt")"
emsdk_dir="${TERMIN_EMSDK_DIR:-$repo_root/build/toolchains/emsdk}"
build_dir="${TERMIN_CORE_WEB_BUILD_DIR:-$repo_root/build/platform/web/wasm32}"
sdk_root="${TERMIN_CORE_WEB_SDK:-$repo_root/sdk-platform/web/wasm32}"
clean=0
setup=0

while (($#)); do
    case "$1" in
        --setup) setup=1; shift ;;
        --build-dir) build_dir="$2"; shift 2 ;;
        --prefix) sdk_root="$2"; shift 2 ;;
        --clean) clean=1; shift ;;
        --help|-h)
            echo "Usage: $0 [--setup] [--build-dir PATH] [--prefix PATH] [--clean]"
            exit 0
            ;;
        *) echo "ERROR: unsupported argument: $1" >&2; exit 2 ;;
    esac
done

if ((setup)); then
    "$repo_root/scripts/build/setup-web-toolchain.sh"
fi
emcmake="$emsdk_dir/upstream/emscripten/emcmake"
emcc="$emsdk_dir/upstream/emscripten/emcc"
if [[ ! -x "$emcmake" || ! -x "$emcc" ]]; then
    echo "ERROR: pinned Emscripten is missing; run $0 --setup" >&2
    exit 1
fi
actual_version="$($emcc --version | head -n 1)"
if [[ "$actual_version" != *" $version "* && "$actual_version" != *" $version" ]]; then
    echo "ERROR: expected Emscripten $version, got: $actual_version" >&2
    exit 1
fi
if ((clean)); then
    cmake -E remove_directory "$build_dir"
    cmake -E remove_directory "$sdk_root"
fi

"$emcmake" cmake -S "$repo_root" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$sdk_root" \
    -DTERMIN_CORE_TARGET_SYSTEM=web \
    -DTERMIN_BUILD_PYTHON=OFF \
    -DTERMIN_BUILD_TESTS=OFF
cmake --build "$build_dir" --parallel "${BUILD_JOBS:-$(nproc)}"
cmake --install "$build_dir"

PYTHONPATH="$repo_root/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m termin_build.platform_sdk write \
        --sdk-root "$sdk_root" \
        --system web \
        --architecture wasm32 \
        --toolchain emscripten \
        --toolchain-version "$version"
PYTHONPATH="$repo_root/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m termin_build.platform_sdk verify \
        --sdk-root "$sdk_root" \
        --system web \
        --architecture wasm32
echo "Termin Core Web SDK: $sdk_root"
