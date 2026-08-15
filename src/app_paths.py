"""
src.app_paths
Resolves the writable base directory shared by every entry point (desktop dev, desktop bundle). Imported before `constants` and `logger` run
their module-level side effects, so it must stay stdlib-only and must not
import anything else from `src`.
"""

import os
import sys

APP_FOLDER_NAME = "MTGA_Draft_Tool"
BASE_DIR_ENV_VAR = "MTGA_DRAFT_BASE_DIR"


def user_data_dir() -> str:
    """The per-user writable location for Sets/, Logs/, Temp/, Debug/, config.json."""
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_FOLDER_NAME}")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(appdata, APP_FOLDER_NAME)
    return os.path.expanduser(f"~/.config/{APP_FOLDER_NAME}")


def resolve_base_dir() -> str:
    """Base dir, creating it if needed. Env override wins so the bundled
    pytauri app can opt in without setting PyInstaller's `sys.frozen`."""
    override = os.environ.get(BASE_DIR_ENV_VAR)
    if override:
        path = override
    elif getattr(sys, "frozen", False):
        path = user_data_dir()
    else:
        path = os.getcwd()

    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception:
            pass
    return path
