### Argument ###

$PYTHON_VERSION = "3.13.7"  # update these by yourself
$TAG = "20250828"  # update these by yourself

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
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue "$TEMP_FILE"
}
