#!/usr/bin/env pwsh
# Build and verify the complete standalone Core repository.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path "termin-thirdparty\guard\guard_main.h" -PathType Leaf)) {
    throw "termin-thirdparty/guard is missing; run git submodule update --init termin-thirdparty/guard"
}

.\build-sdk.ps1 --no-pch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

cmake -S . -B build\Tests `
    -DTERMIN_BUILD_TESTS=ON `
    -DTERMIN_BUILD_PYTHON=OFF `
    -DTERMIN_ENABLE_PCH=OFF
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmake --build build\Tests --config Release
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
ctest --test-dir build\Tests -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\setup-sdk-python-env.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\sdk\bin\termin_python.exe `
    --termin-overlay build\python-envs\test\overlay.json `
    -m pytest -q `
    termin-base\tests\python `
    termin-dispatch\tests\python `
    termin-inspect\tests `
    termin-mcp\tests `
    termin-nanobind-sdk\tests `
    termin-build-tools\tests\test_artifact_manifest.py `
    termin-build-tools\tests\test_local_wheel_artifacts.py `
    termin-build-tools\tests\test_product_manifest.py `
    termin-build-tools\tests\test_python_abi.py `
    termin-build-tools\tests\test_python_overlay.py `
    termin-build-tools\tests\test_python_test_environment.py `
    termin-build-tools\tests\test_python_toolchain.py `
    termin-build-tools\tests\test_relocated_sdk_smoke.py `
    termin-build-tools\tests\test_sdk_profiles.py `
    termin-build-tools\tests\test_sdk_release.py `
    termin-build-tools\tests\test_source_size_policy.py `
    termin-build-tools\tests\test_wheelhouse.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\sdk\bin\termin_python.exe -I scripts\smoke-installed-core-consumers --sdk-root sdk
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\sdk\bin\termin_python.exe -m termin_build.relocated_sdk_smoke --sdk-root sdk
exit $LASTEXITCODE
