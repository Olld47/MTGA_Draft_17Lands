#!/usr/bin/env bash
# Local build entrypoint for the PyTauri desktop app (desktop/).
#
# Detects the host OS and dispatches to the platform-specific scripts under
# desktop/scripts/, mirroring the desktop CI workflows
# (.github/workflows/build-desktop-{macos,windows}.yml). CI keeps calling the
# platform scripts directly; this is the one-command entry point for local
# builds. Run ./build_desktop.sh from the repo root (macOS) or from Git Bash /
# WSL (Windows).
#
# Supported platforms: macOS arm64 and Windows x86_64. The other two target
# combos are deliberately absent because numba 0.65.1 publishes no wheel for
# them (see the workflow comments). Linux is not a desktop target.
#
# Requirements: uv, Node.js + npm, and Rust (rustup) with the host target
# installed.

set -euo pipefail
cd "$(dirname "$0")"

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required tool: $1" >&2
    echo "the desktop build needs uv, Node.js/npm, and Rust" >&2
    exit 1
  fi
}

OS="$(uname -s)"
case "$OS" in
  Darwin)
    require uv
    require node
    require npm
    require cargo
    require rustc

    # python-build-standalone only needs fetching once; CI re-downloads it on
    # every run because it starts from a fresh checkout.
    if [[ ! -x desktop/src-tauri/pyembed/python/bin/python3 ]]; then
      desktop/scripts/macos/download-py.sh aarch64-apple-darwin
    fi

    # CI=true makes tauri-bundler pass --skip-jenkins to bundle_dmg.sh, which
    # skips the Finder-prettifying AppleScript that needs a GUI session. Local
    # builds (terminal/SSH/agents) have no Finder, so without this the DMG step
    # fails after the .app is built. This is exactly what the CI runner does.
    CI=true desktop/scripts/macos/build.sh
    ;;

  MINGW* | MSYS* | CYGWIN*)
    require uv
    require node
    require npm
    require cargo
    require rustc

    if [[ ! -f desktop/src-tauri/pyembed/python/python.exe ]]; then
      powershell.exe -NoProfile -ExecutionPolicy Bypass \
        -File desktop/scripts/windows/download-py.ps1 x86_64-pc-windows-msvc
    fi
    powershell.exe -NoProfile -ExecutionPolicy Bypass \
      -File desktop/scripts/windows/build.ps1
    ;;

  *)
    echo "unsupported platform: $OS" >&2
    echo "the desktop app builds on macOS arm64 or Windows x86_64 only" >&2
    exit 1
    ;;
esac

echo "build finished: see desktop/target/bundle-release/bundle/"
