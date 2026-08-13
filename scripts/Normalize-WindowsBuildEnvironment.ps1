function Normalize-WindowsBuildEnvironment {
    # Keep the entry point shared by the Windows build and test scripts.  In
    # particular, do not import a Visual Studio environment here: CMake is
    # responsible for selecting and initializing its generator/toolchain.
    if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
            [System.Runtime.InteropServices.OSPlatform]::Windows)) {
        return
    }

    # Git and some archive tools can leave quoted PATH entries behind.  Native
    # process lookup treats the quote as part of the directory name.
    if ($env:PATH) {
        $env:PATH = (($env:PATH -split [IO.Path]::PathSeparator | ForEach-Object {
                    $_.Trim().Trim('"')
                } | Where-Object { $_ }) -join [IO.Path]::PathSeparator)
    }
}
