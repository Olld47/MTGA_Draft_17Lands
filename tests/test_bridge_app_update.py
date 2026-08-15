"""
tests/test_bridge_app_update.py
Behavioural tests for mtga_bridge.app_update_notifier — the per-launch check
for a newer desktop release that mirrors the legacy tkinter AppUpdate poller.

Every test runs check_app_update synchronously (time.sleep patched), so the 3s
delay never blocks the suite. Network access is mocked at requests.get, so no
HTTP call ever leaves the test process.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Make the bridge package importable from the root test run
BRIDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "desktop",
    "src-tauri",
    "src-python",
)
if BRIDGE_PATH not in sys.path:
    sys.path.insert(0, BRIDGE_PATH)

from mtga_bridge.app_update_notifier import (
    EVENT_APP_UPDATE_AVAILABLE,
    RELEASES_FALLBACK_URL,
    _parse_version,
    check_app_update,
)
from mtga_bridge.version import DESKTOP_VERSION
from mtga_bridge.viewmodels import AppUpdateAvailableVM, _VM


def _current_tag():
    """The app's own release tag (e.g. 'v1.0.0')."""
    return f"v{DESKTOP_VERSION}"


def _newer_tag():
    """A tag one patch above the app's own version — guaranteed newer than
    _CURRENT for any current version, so these tests survive version bumps."""
    major, minor, patch = _parse_version(DESKTOP_VERSION)
    return f"v{major}.{minor}.{patch + 1}"


class Recorder:
    """Stands in for the Emitter.emit closure __init__.py builds."""

    def __init__(self):
        self.events = []

    def __call__(self, event, payload):
        self.events.append((event, payload))


class FakeResponse:
    """requests.get return value: raise_for_status gates json() like the real
    client, so a non-2xx is testable without a running server."""

    def __init__(self, status_code=200, payload=None):
        self._status = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")

    def json(self):
        return self._payload


@pytest.fixture
def emit():
    return Recorder()


@pytest.fixture
def requests_mock(monkeypatch):
    """Install a requests.get stub plus a no-op time.sleep so the 3s delay
    never blocks. Returns the stub for call-assertions."""

    def _install(response=None, side_effect=None):
        stub = MagicMock(return_value=response, side_effect=side_effect)
        monkeypatch.setattr("requests.get", stub)
        monkeypatch.setattr(
            "mtga_bridge.app_update_notifier.time.sleep", MagicMock()
        )
        return stub

    return _install


def _release(tag, html_url="https://github.com/unrealities/MTGA_Draft_17Lands/releases"):
    return {"tag_name": tag, "html_url": html_url}


# --- _parse_version ----------------------------------------------------------


def test_parse_version_normalizes_for_comparison():
    assert _parse_version("0.39.0") == (0, 39, 0)
    assert _parse_version("0.40") == (0, 40, 0)  # zero-pad
    assert _parse_version("0.39.0.1") == (0, 39, 0)  # truncate to 3 parts
    assert _parse_version("0.40.0-beta.1") == (0, 40, 0)  # drop prerelease
    assert _parse_version("") is None
    assert _parse_version("beta") is None


# --- check_app_update --------------------------------------------------------


def test_a_newer_release_emits_the_update_event(emit, requests_mock):
    tag = _newer_tag()
    requests_mock(FakeResponse(payload=_release(tag)))

    check_app_update(object(), emit)

    assert emit.events == [
        (
            EVENT_APP_UPDATE_AVAILABLE,
            AppUpdateAvailableVM(latest_version=tag, release_url=_release(tag)["html_url"]),
        )
    ]
    payload = emit.events[0][1]
    assert isinstance(payload, _VM)


def test_the_current_version_emits_nothing(emit, requests_mock):
    requests_mock(FakeResponse(payload=_release(_current_tag())))

    check_app_update(object(), emit)

    assert emit.events == []


def test_an_older_release_emits_nothing(emit, requests_mock):
    requests_mock(FakeResponse(payload=_release("v0.38.2")))

    check_app_update(object(), emit)

    assert emit.events == []


def test_a_non_2xx_response_is_silent(emit, requests_mock):
    requests_mock(FakeResponse(status_code=500))

    check_app_update(object(), emit)  # must not raise

    assert emit.events == []


def test_a_network_failure_is_silent(emit, requests_mock):
    requests_mock(side_effect=RuntimeError("no network"))

    check_app_update(object(), emit)  # must not raise

    assert emit.events == []


def test_a_missing_or_malformed_tag_is_silent(emit, requests_mock):
    requests_mock(FakeResponse(payload=_release("")))
    check_app_update(object(), emit)
    assert emit.events == []

    requests_mock(FakeResponse(payload=_release("not-a-version")))
    check_app_update(object(), emit)
    assert emit.events == []


def test_a_missing_html_url_falls_back_to_the_releases_page(emit, requests_mock):
    requests_mock(FakeResponse(payload={"tag_name": _newer_tag()}))

    check_app_update(object(), emit)

    assert emit.events[0][1].release_url == RELEASES_FALLBACK_URL


def test_the_request_uses_a_descriptive_user_agent(emit, requests_mock):
    stub = requests_mock(FakeResponse(payload=_release(_newer_tag())))

    check_app_update(object(), emit)

    headers = stub.call_args.kwargs["headers"]["User-Agent"]
    assert headers.startswith(f"MTGADraftTool/{DESKTOP_VERSION}")
    assert "unrealities/MTGA_Draft_17Lands" in headers
