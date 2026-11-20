### Argument ###

$PYTHON_VERSION = "3.13.18"  # update these by yourself
$TAG = "20261110"  # update these by yourself

################

$ErrorActionPreference = "Stop"

$TARGET = if ($args.Count -ge 1) { $args[0] } else { "x86_64-pc-windows-msvc" }

Set-Location (Resolve-Path "$PSScriptRoot\..\..")

$url = "https://github.com/astral-sh/python-build-standalone/releases/download/${TAG}/cpython-${PYTHON_VERSION}+${TAG}-${TARGET}-install_only_stripped.tar.gz"

$DEST_DIR = "src-tauri\pyembed"
$TEMP_FILE = ".python-standalone.tar.gz"
try {
    # -f so an HTTP error page is not silently unpacked as a tarball; native
    # exit codes do not trip $ErrorActionPreference, so check them by hand.
    curl.exe -fL "$url" -o "$TEMP_FILE"
    if ($LASTEXITCODE -ne 0) { throw "curl failed ($LASTEXITCODE) for $url" }

    if (Test-Path $DEST_DIR) { Remove-Item -Recurse -Force $DEST_DIR }
    New-Item -ItemType Directory -Path $DEST_DIR -Force | Out-Null

    tar.exe -xzf "$TEMP_FILE" -C "$DEST_DIR"
    if ($LASTEXITCODE -ne 0) { throw "tar failed ($LASTEXITCODE)" }

    # The bundle's resource mapping copies pyembed/python into the .exe's own
    # directory, so these DLLs must exist at the archive root. Assert it here:
    # otherwise a changed archive surfaces ~12 minutes later as "no python3*.dll
    # beside the exe", which does not say where the file went missing.
    foreach ($required in @("python.exe", "python3.dll")) {
        if (-not (Test-Path -LiteralPath "$DEST_DIR\python\$required")) {
            Get-ChildItem "$DEST_DIR\python" | Format-Table Name | Out-String | Write-Host
            throw "downloaded archive has no python\$required at its root"
        }
    }
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue "$TEMP_FILE"
}
