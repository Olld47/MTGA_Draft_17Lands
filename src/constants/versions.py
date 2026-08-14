"""Application version literals (tkinter series).

Single point of edit for the frozen tkinter 4.x series. `bump_version.py`
rewrites these with regexes — keep the assignment shapes stable.
"""

APPLICATION_VERSION = "4.19"
OLD_APPLICATION_VERSION = "4.17"
PREVIOUS_APPLICATION_VERSION = "0418"

__all__ = [
    "APPLICATION_VERSION",
    "OLD_APPLICATION_VERSION",
    "PREVIOUS_APPLICATION_VERSION",
]
