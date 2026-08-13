param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string[]]$RequiredPaths
)

foreach ($relativePath in $RequiredPaths) {
    $path = Join-Path $RepoRoot $relativePath
    if (Test-Path -LiteralPath $path -PathType Container) {
        $contents = Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop |
            Select-Object -First 1
        if ($contents) {
            continue
        }
    }

    & git -C $RepoRoot submodule update --init --recursive -- $relativePath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to initialize required third-party path: $relativePath"
    }
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Required third-party path is missing after initialization: $relativePath"
    }
}
