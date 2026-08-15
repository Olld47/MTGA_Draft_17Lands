"""Application version literals.

`APPLICATION_VERSION` is retained as the bootstrap migration marker for
`config.settings.last_run_version` (src.bootstrap); it is not a release
version — the desktop series is single-sourced from tauri.conf.json.
Keep the assignment shapes stable (test_constants_package pins them).
"""

APPLICATION_VERSION = "4.19"
OLD_APPLICATION_VERSION = "4.17"
PREVIOUS_APPLICATION_VERSION = "0418"

__all__ = [
    "APPLICATION_VERSION",
    "OLD_APPLICATION_VERSION",
    "PREVIOUS_APPLICATION_VERSION",
]
