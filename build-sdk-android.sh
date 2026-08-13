#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
android_abi="${ANDROID_ABI:-arm64-v8a}"
android_api="${ANDROID_PLATFORM:-android-26}"
ndk_root="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
build_dir=""
sdk_root=""
clean=0

while (($#)); do
    case "$1" in
        --abi) android_abi="$2"; shift 2 ;;
        --api|--platform) android_api="$2"; shift 2 ;;
        --ndk) ndk_root="$2"; shift 2 ;;
        --build-dir) build_dir="$2"; shift 2 ;;
        --prefix) sdk_root="$2"; shift 2 ;;
        --clean) clean=1; shift ;;
        --help|-h)
            echo "Usage: $0 [--abi ABI] [--api android-N] [--ndk PATH] [--build-dir PATH] [--prefix PATH] [--clean]"
            exit 0
            ;;
        *) echo "ERROR: unsupported argument: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "$ndk_root" ]]; then
    echo "ERROR: Android NDK is required via --ndk, ANDROID_NDK_HOME or ANDROID_NDK_ROOT" >&2
    exit 1
fi
ndk_root="$(cd "$ndk_root" && pwd)"
toolchain="$ndk_root/build/cmake/android.toolchain.cmake"
if [[ ! -f "$toolchain" ]]; then
    echo "ERROR: Android CMake toolchain is missing: $toolchain" >&2
    exit 1
fi
build_dir="${build_dir:-$repo_root/build/platform/android/$android_abi}"
sdk_root="${sdk_root:-$repo_root/sdk-platform/android/$android_abi}"
if ((clean)); then
    cmake -E remove_directory "$build_dir"
    cmake -E remove_directory "$sdk_root"
fi

ndk_version="$(sed -n 's/^Pkg.Revision[[:space:]]*=[[:space:]]*//p' "$ndk_root/source.properties" | head -n 1)"
if [[ -z "$ndk_version" ]]; then
    echo "ERROR: cannot determine Android NDK version from $ndk_root/source.properties" >&2
    exit 1
fi

cmake -S "$repo_root" -B "$build_dir" \
    -DCMAKE_TOOLCHAIN_FILE="$toolchain" \
    -DANDROID_ABI="$android_abi" \
    -DANDROID_PLATFORM="$android_api" \
    -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$sdk_root" \
    -DTERMIN_CORE_TARGET_SYSTEM=android \
    -DTERMIN_BUILD_PYTHON=OFF \
    -DTERMIN_BUILD_TESTS=OFF
cmake --build "$build_dir" --parallel "${BUILD_JOBS:-$(nproc)}"
cmake --install "$build_dir"

PYTHONPATH="$repo_root/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m termin_build.platform_sdk write \
        --sdk-root "$sdk_root" \
        --system android \
        --architecture "$android_abi" \
        --api "$android_api" \
        --toolchain android-ndk \
        --toolchain-version "$ndk_version"
PYTHONPATH="$repo_root/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m termin_build.platform_sdk verify \
        --sdk-root "$sdk_root" \
        --system android \
        --architecture "$android_abi"
echo "Termin Core Android SDK: $sdk_root"
