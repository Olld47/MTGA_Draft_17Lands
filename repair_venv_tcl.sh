#!/usr/bin/env bash
# Repair the root test venv so `./.venv/bin/python -m pytest` works.
#
# Why: uv's rolling `cpython-3.13` build ships no Tcl scripts (built against a
# builder sandbox path), so tkinter.Tk() raises TclError the moment pytest's
# session fixture creates a root. The pinned `cpython-3.13.9` build bundles a
# working Tcl/Tk. A venv still sets sys.prefix to itself, so even pointing at
# the good build needs its Tcl/Tk script trees linked into the venv.
#
# Idempotent: safe to re-run after any `uv venv` rebuild. macOS-only (sed -i '').
set -euo pipefail

cd "$(dirname "$0")"

GOOD_PY="$HOME/.local/share/uv/python/cpython-3.13.9-macos-aarch64-none"
if [[ ! -x "$GOOD_PY/bin/python3.13" ]]; then
    echo "missing $GOOD_PY — run 'uv python install 3.13.9' first" >&2
    exit 1
fi

ln -sfn "$GOOD_PY/bin/python3.13" .venv/bin/python
sed -i '' "s|^home = .*|home = $GOOD_PY/bin|" .venv/pyvenv.cfg
mkdir -p .venv/lib
ln -sfn "$GOOD_PY/lib/tcl8.6" .venv/lib/tcl8.6
ln -sfn "$GOOD_PY/lib/tk8.6" .venv/lib/tk8.6

.venv/bin/python -c "import tkinter; tkinter.Tk().destroy(); print('venv Tk OK')"
