"""
mtga_bridge.app_update_notifier
Once per launch, ~3s after boot, check the latest GitHub release tag against the
desktop's own version and emit update://available with the newest version and
its Releases page URL when a newer desktop release exists. No auto-download —
the toast links to the Releases page and the user grabs the bundle there.
Runs on a daemon thread (see mtga_bridge.boot) so boot never blocks on it and
shutdown never joins it.

Kept pytauri-free and import-light so it can be pytest-ed from the root poetry
environment; the HTTP client and the VM are deferred to call time.
"""

import logging
import re
import time

from mtga_bridge.version import DESKTOP_VERSION

logger = logging.getLogger(__name__)

EVENT_APP_UPDATE_AVAILABLE = "update://available"
UPDATE_LATEST_URL = (
    "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest"
)
RELEASES_FALLBACK_URL = (
    "https://github.com/unrealities/MTGA_Draft_17Lands/releases"
)

# GitHub's releases/latest never returns prereleases, and the capture strips any
# leading "v" plus anything before the first dotted number ("v0.39.0" -> 0.39.0).
_VERSION_RE = re.compile(r"v?(\d+(?:\.\d+)+)")


def _parse_version(s: str):
    """Normalize a version string to a 3-component int tuple for comparison.

    Splits on "-" first so prerelease/build metadata ("0.40.0-beta.1") never
    pollutes the numbers, dot-splits, ints, truncates to the first three
    components ("0.39.0.1" -> (0, 39, 0)) and zero-pads ("0.40" -> (0, 40, 0)).
    Unparsable input returns None so callers can stay silent.
    """
    numbers = re.findall(r"\d+", s.split("-", 1)[0])
    if not numbers:
        return None
    parts = [int(n) for n in numbers[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


_CURRENT = _parse_version(DESKTOP_VERSION)


def check_app_update(runtime, emit, delay: float = 3.0) -> None:
    """Sleep `delay`, fetch the latest GitHub release, and emit
    update://available when its tag is newer than DESKTOP_VERSION.

    Silent on every failure: this runs on a daemon thread after boot completed,
    so a network error must never surface to the user — a failed update check is
    not an app error. `emit` must keep that parameter name: the emit-site AST
    walk (test_emit_sites_construct_a_model) counts call sites whose payload is
    a _VM constructor, and we want this module in that sweep.
    """
    time.sleep(delay)
    try:
        import requests

        resp = requests.get(
            UPDATE_LATEST_URL,
            headers={
                "User-Agent": (
                    f"MTGADraftTool/{DESKTOP_VERSION} "
                    "(Educational Tool; https://github.com/unrealities/"
                    "MTGA_Draft_17Lands)"
                )
            },
            timeout=5,
        )
        resp.raise_for_status()
        release = resp.json()
    except Exception as e:
        logger.warning(f"App update check failed: {e}")
        return

    match = _VERSION_RE.search(release.get("tag_name", "") or "")
    latest = _parse_version(match.group(1)) if match else None
    if latest and latest > _CURRENT:
        from mtga_bridge.viewmodels import AppUpdateAvailableVM

        emit(
            EVENT_APP_UPDATE_AVAILABLE,
            AppUpdateAvailableVM(
                latest_version=release.get("tag_name", "") or "",
                release_url=release.get("html_url") or RELEASES_FALLBACK_URL,
            ),
        )
