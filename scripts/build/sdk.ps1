#!/usr/bin/env pwsh
# Build the standalone Termin Core SDK through the shared Python orchestrator.

$ErrorActionPreference = "Stop"
$ScriptDir = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
. (Join-Path $ScriptDir "scripts\Normalize-WindowsSdkPermissions.ps1")

$pythonCommand = $null
foreach ($candidate in @($env:PYTHON_BIN, $env:PYTHON_EXECUTABLE, "python", "python3")) {
    if ($candidate -and -not $pythonCommand) {
        $pythonCommand = Get-Command $candidate -ErrorAction SilentlyContinue
    }
}
if (-not $pythonCommand) {
    throw "Python executable not found in PATH"
}

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $ScriptDir "termin-build-tools"
if ($oldPythonPath) {
    $env:PYTHONPATH = "$env:PYTHONPATH$([IO.Path]::PathSeparator)$oldPythonPath"
}

& $pythonCommand.Source -m termin_build.sdk --repo-root $ScriptDir build @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$sdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $ScriptDir "sdk" }
Enable-TerminSdkInheritedPermissions -SdkPrefix $sdkPrefix
