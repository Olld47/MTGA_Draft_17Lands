#!/bin/bash

set -e

cd "$(dirname "$0")/../.."

REPO_ROOT="$(cd .. && pwd)"
PYLIB_DIR="$(realpath src-tauri/pyembed/python/lib)"

export PYTAURI_STANDALONE="1"
export PYO3_PYTHON="$(realpath src-tauri/pyembed/python/bin/python3)"
export RUSTFLAGS=" \
    -C link-arg=-Wl,-rpath,@executable_path/../Resources/lib \
    -L $PYLIB_DIR"

uv pip install \
    --exact \
    --compile-bytecode \
    --python="$PYO3_PYTHON" \
    --reinstall-package="mtga-bridge" \
    ./src-tauri

# The bridge imports the repo-root `src` package, so it has to live in the
# embedded interpreter too. --no-deps keeps the tkinter-only requirements
# (ttkbootstrap, pynput, pywin32) out of the bundle; the shared runtime pins
# already arrived with mtga-bridge above. Runs after the --exact install,
# which would otherwise prune it.
uv pip install \
    --no-deps \
    --compile-bytecode \
    --python="$PYO3_PYTHON" \
    --reinstall-package="mtga-draft-tool" \
    "$REPO_ROOT"

npm run tauri -- build --config="src-tauri/tauri.bundle.json" -- --profile bundle-release
