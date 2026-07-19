"""
mtga_bridge.paths
Locates the repository root and pins the process working directory before any
`src.*` import happens. `src/constants.py` derives BASE_DIR (Sets/, Logs/,
Temp/) from os.getcwd() in non-frozen mode, so both UIs must agree on cwd or
their data folders silently fork.
"""

import os
import sys


def find_repo_root() -> str:
    """Walks up from this file until it finds the repo root (contains src/constants.py)."""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.exists(os.path.join(current, "src", "constants.py")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError(
                "Could not locate the MTGA_Draft_17Lands repo root from "
                f"{os.path.abspath(__file__)}"
            )
        current = parent


def ensure_cwd() -> str:
    """Chdir to the repo root and make `src` importable. Returns the root path.

    Must run BEFORE the first `import src.constants` anywhere in the process.
    """
    root = find_repo_root()
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)

    # Sanity check: constants must resolve its folders under the root we chose.
    from src import constants

    sets_folder = os.path.abspath(constants.SETS_FOLDER)
    if not sets_folder.startswith(os.path.abspath(constants.BASE_DIR)):
        raise RuntimeError(
            f"SETS_FOLDER {sets_folder} escaped BASE_DIR {constants.BASE_DIR}"
        )
    return root
