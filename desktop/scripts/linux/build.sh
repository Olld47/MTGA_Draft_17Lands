#!/bin/bash

set -e

cd "$(dirname "$0")/../.."

# The deb/rpm resource dir is `/usr/lib/<productName>`, verbatim — the bundler
# does not slugify it (tauri-bundler `debian.rs` joins `settings.product_name()`)
# and `resource_dir()` resolves the same name at runtime. So this must track
# tauri.conf.json's productName, NOT the Cargo [[bin]] name. Read rather than
# duplicated so the two cannot drift; `tests/test_desktop_bundle_config.py`
# additionally pins productName to be whitespace-free, since RUSTFLAGS is
# split on spaces and a space here would truncate the rpath.
PRODUCT_NAME="$(
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["productName"])' \
        src-tauri/tauri.conf.json
)"
REPO_ROOT="$(cd .. && pwd)"
PYLIB_DIR="$(realpath src-tauri/pyembed/python/lib)"

export PYTAURI_STANDALONE="1"
export PYO3_PYTHON="$(realpath src-tauri/pyembed/python/bin/python3)"
export RUSTFLAGS=" \
    -C link-arg=-Wl,-rpath,\$ORIGIN/../lib/$PRODUCT_NAME/lib \
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
