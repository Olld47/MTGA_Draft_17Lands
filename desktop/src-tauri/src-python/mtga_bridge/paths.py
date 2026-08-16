"""
mtga_bridge.paths
Pins the process working directory and `src` importability before any `src.*`
import happens. `src/constants` derives BASE_DIR (Sets/, Logs/, Temp/) from
the cwd in a source checkout, so both UIs must agree on cwd or their data
folders silently fork.

Two modes, distinguished by whether a repo root is found above this file:

- Source checkout: chdir to the repo root and put it on sys.path. A directory
  only counts as a checkout when it also has the poetry project markers
  (`pyproject.toml`, `main.py`) — the bundle's site-packages contains `src/`
  too, so `src/constants` alone must not trigger this branch.
- Bundled app: `src` is installed in the embedded interpreter's site-packages
  (side by side with `mtga_bridge`, no project markers), and the cwd of a
  launched .app is "/", so point BASE_DIR at the per-user data dir.
"""

import os
import sys
from typing import Optional


def find_repo_root() -> Optional[str]:
    """Walks up from this file looking for the repo root.

    A directory only counts as the checkout when it carries the poetry project
    markers (`pyproject.toml`, `main.py`) NEXT TO `src/constants/`. The bare
    `src/constants` probe is not enough: the bundle build installs the repo-root
    `src` package into the embedded interpreter's site-packages, right beside
    `mtga_bridge`, so a walk-up from `site-packages/mtga_bridge/` finds
    `site-packages/src/constants` and would misclassify the packaged app as a
    source checkout — relocating Sets/, Logs/, Temp/ and config.json inside the
    .app bundle, where an update wipes them.

    Returns None when running from a bundle, where `src` lives in the embedded
    interpreter's site-packages rather than above this file.
    """
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if (
            os.path.isdir(os.path.join(current, "src", "constants"))
            and os.path.isfile(os.path.join(current, "pyproject.toml"))
            and os.path.isfile(os.path.join(current, "main.py"))
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def ensure_runtime_paths() -> str:
    """Pin cwd and `src` importability. Returns the resolved base directory.

    Must run BEFORE the first `import src.constants` anywhere in the process.
    """
    root = find_repo_root()
    if root is not None:
        os.chdir(root)
        if root not in sys.path:
            sys.path.insert(0, root)
    else:
        from src.app_paths import BASE_DIR_ENV_VAR, user_data_dir

        base_dir = os.environ.setdefault(BASE_DIR_ENV_VAR, user_data_dir())
        os.makedirs(base_dir, exist_ok=True)
        os.chdir(base_dir)
        root = base_dir

    # Sanity check: constants must resolve its folders under the root we chose.
    from src import constants

    sets_folder = os.path.abspath(constants.SETS_FOLDER)
    if not sets_folder.startswith(os.path.abspath(constants.BASE_DIR)):
        raise RuntimeError(
            f"SETS_FOLDER {sets_folder} escaped BASE_DIR {constants.BASE_DIR}"
        )
    return root
