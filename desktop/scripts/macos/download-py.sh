#!/bin/bash

### Argument ###

PYTHON_VERSION="3.13.18"  # update these by yourself
TAG="20261110"  # update these by yourself

################

set -eo pipefail

# python-build-standalone spells Apple Silicon "aarch64"; uname says "arm64".
ARCH="$(uname -m)"
[ "$ARCH" = "arm64" ] && ARCH="aarch64"
TARGET="${1:-$ARCH-apple-darwin}"

cd "$(dirname "$0")/../.."

url="https://github.com/astral-sh/python-build-standalone/releases/download/${TAG}/cpython-${PYTHON_VERSION}+${TAG}-${TARGET}-install_only_stripped.tar.gz"

DEST_DIR="src-tauri/pyembed"
rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
curl -fL "$url" | tar -xz -C "$DEST_DIR"

python_major_minor="${PYTHON_VERSION%.*}"  # "3.13.18" -> "3.13"

# Assert the archive's layout before anything downstream depends on it. A changed
# archive otherwise surfaces much later as a missing interpreter or dylib, which
# does not say where it went missing.
for required in \
    "python/bin/python3" \
    "python/lib/libpython$python_major_minor.dylib"; do
    if [ ! -e "$DEST_DIR/$required" ]; then
        ls -la "$DEST_DIR/python" >&2 || true
        echo "downloaded archive has no $required" >&2
        exit 1
    fi
done

# ref: <https://github.com/pytauri/pytauri/issues/99#issuecomment-2704556726>
install_name_tool -id "@rpath/libpython$python_major_minor.dylib" "$DEST_DIR/python/lib/libpython$python_major_minor.dylib"
