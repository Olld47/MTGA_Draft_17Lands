$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..\..")

$REPO_ROOT = (Resolve-Path "..").Path

$env:PYTAURI_STANDALONE = "1"
$env:PYO3_PYTHON = (Resolve-Path -LiteralPath "src-tauri\pyembed\python\python.exe").Path

# $ErrorActionPreference does not apply to native executables, so every
# uv.exe / npm call needs its exit code checked or a failed install would
# still produce a bundle.
uv.exe pip install `
    --exact `
    --compile-bytecode `
    --python="$env:PYO3_PYTHON" `
    --reinstall-package="mtga-bridge" `
    .\src-tauri
if ($LASTEXITCODE -ne 0) { throw "uv pip install mtga-bridge failed ($LASTEXITCODE)" }

# The bridge imports the repo-root `src` package, so it has to live in the
# embedded interpreter too. --no-deps keeps the tkinter-only requirements
# (ttkbootstrap, pynput, pywin32) out of the bundle; the shared runtime pins
# already arrived with mtga-bridge above. Runs after the --exact install,
# which would otherwise prune it.
uv.exe pip install `
    --no-deps `
    --compile-bytecode `
    --python="$env:PYO3_PYTHON" `
    --reinstall-package="mtga-draft-tool" `
    "$REPO_ROOT"
if ($LASTEXITCODE -ne 0) { throw "uv pip install mtga-draft-tool failed ($LASTEXITCODE)" }

npm run tauri -- build --config="src-tauri\tauri.bundle.json" -- --profile bundle-release
if ($LASTEXITCODE -ne 0) { throw "tauri build failed ($LASTEXITCODE)" }
