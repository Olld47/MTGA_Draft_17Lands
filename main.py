"""
main.py
MTGA Draft Tool - Entry Point.

Convenience launcher for the built desktop app (PyTauri), which is the only
client. Resolves the desktop binary (MTGA_DRAFT_DESKTOP env var, the bundled
.app on macOS, then the cargo release/debug targets), forwards `-f`/`-d`
verbatim, and hands control over. There is no fallback UI: if no desktop
build exists the process prints build/dev guidance and exits 2.
"""

import argparse
import os
import subprocess
import sys
import logging
from typing import List, Optional
from src import constants
from src.configuration import read_configuration
from src.bootstrap import cleanup_old_draft_logs

logger = logging.getLogger(__name__)


def find_desktop_launcher() -> Optional[str]:
    """Return a runnable desktop binary path, or None if none is built.

    Probe order: MTGA_DRAFT_DESKTOP env var, then the bundled .app on macOS,
    then the cargo release/debug binaries. The env var may be a file or, on
    macOS, an .app directory (whose inner binary is then probed).
    """
    candidates: List[str] = []
    env = os.environ.get("MTGA_DRAFT_DESKTOP")
    if env:
        candidates.append(env)
        if sys.platform == "darwin" and os.path.isdir(env):
            candidates.append(
                os.path.join(env, "Contents", "MacOS", "mtga-draft-desktop")
            )
    if sys.platform == "darwin":
        candidates.append(
            os.path.join(
                constants.BASE_DIR,
                "desktop",
                "target",
                "bundle-release",
                "bundle",
                "macos",
                "mtga-draft-desktop.app",
                "Contents",
                "MacOS",
                "mtga-draft-desktop",
            )
        )
    exe = ".exe" if sys.platform == "win32" else ""
    for build_dir in ("release", "debug"):
        candidates.append(
            os.path.join(
                constants.BASE_DIR,
                "desktop",
                "target",
                build_dir,
                f"mtga-draft-desktop{exe}",
            )
        )
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def launch_desktop(binary: str, file: Optional[str] = None, data: Optional[str] = None):
    """Spawn the desktop app detached and hand control to it. `-f/-d` are
    forwarded verbatim (mtga_bridge.boot._parse_cli_args mirrors them)."""
    argv = [binary]
    if file:
        argv += ["-f", file]
    if data:
        argv += ["-d", data]
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(argv, **kwargs)
    sys.exit(0)


def main():
    # 30-day draft log cleanup
    cleanup_old_draft_logs()

    # CLI Argument Parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Path to Player.log")
    parser.add_argument("-d", "--data", help="Path to MTGA Data")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args, _ = parser.parse_known_args()

    # --- CI/CD SMOKE TEST EXIT ---
    # Instantly validates all imports and exits safely.
    if args.version:
        print(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        sys.exit(0)

    # Load Config — keeps config initialization and corruption detection on
    # the boot path; the desktop app re-reads the same file itself.
    read_configuration()

    launcher = find_desktop_launcher()
    if launcher:
        logger.info(f"Launching desktop app: {launcher}")
        launch_desktop(launcher, args.file, args.data)

    print(
        "No desktop build found. Build or locate one first:\n"
        "  - dev:    cd desktop && npm run tauri dev\n"
        "  - build:  ./build_desktop.sh\n"
        "  - or set MTGA_DRAFT_DESKTOP to the binary."
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
