#!/bin/bash
# Build and verify the complete standalone Core repository.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f termin-thirdparty/guard/guard_main.h ]]; then
    echo "ERROR: termin-thirdparty/guard is missing." >&2
    echo "Run: git submodule update --init termin-thirdparty/guard" >&2
    exit 1
fi

./build-sdk.sh

cmake -S . -B build/Tests \
    -DCMAKE_BUILD_TYPE=Release \
    -DTERMIN_BUILD_TESTS=ON \
    -DTERMIN_BUILD_PYTHON=OFF \
    -DTERMIN_ENABLE_PCH=OFF
cmake --build build/Tests --parallel "${BUILD_JOBS:-$(nproc)}"
ctest --test-dir build/Tests --output-on-failure

./setup-sdk-python-env.sh
./sdk/bin/termin_python \
    --termin-overlay build/python-envs/test/overlay.json \
    -m pytest -q \
    termin-base/tests/python \
    termin-dispatch/tests/python \
    termin-inspect/tests \
    termin-mcp/tests \
    termin-nanobind-sdk/tests \
    termin-build-tools/tests/test_artifact_manifest.py \
    termin-build-tools/tests/test_local_wheel_artifacts.py \
    termin-build-tools/tests/test_product_manifest.py \
    termin-build-tools/tests/test_python_abi.py \
    termin-build-tools/tests/test_python_overlay.py \
    termin-build-tools/tests/test_python_test_environment.py \
    termin-build-tools/tests/test_python_toolchain.py \
    termin-build-tools/tests/test_relocated_sdk_smoke.py \
    termin-build-tools/tests/test_sdk_profiles.py \
    termin-build-tools/tests/test_sdk_release.py \
    termin-build-tools/tests/test_source_size_policy.py \
    termin-build-tools/tests/test_wheelhouse.py

./sdk/bin/termin_python -I scripts/smoke-installed-core-consumers --sdk-root sdk
./sdk/bin/termin_python -m termin_build.relocated_sdk_smoke --sdk-root sdk
