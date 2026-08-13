function Invoke-TerminCMakeBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildDir,

        [Parameter(Mandatory = $true)]
        [string]$BuildType,

        [string[]]$Target,

        [Parameter(Mandatory = $true)]
        [ValidateRange(1, [int]::MaxValue)]
        [int]$BuildJobs
    )

    $arguments = @("--build", $BuildDir, "--config", $BuildType)
    if ($Target) {
        $arguments += "--target"
        $arguments += $Target
    }
    $arguments += @("--parallel", $BuildJobs)

    & cmake @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "cmake build failed with exit code $LASTEXITCODE"
    }
}
