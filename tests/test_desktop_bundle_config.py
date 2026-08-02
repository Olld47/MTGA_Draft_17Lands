"""
tests/test_desktop_bundle_config.py

Guards the desktop bundling contract, which no other test reaches.

The bundle is assembled by an overlay config plus a pair of shell scripts, and
the pieces have to agree on three things: that the overlay actually maps the
embedded interpreter into the bundle, that the workflows call the shared
scripts rather than reimplementing them, and that the artifact names and paths
the workflows glob are the ones the build profile produces.

These assertions are cheap; the failures they prevent surface only after a full
CI build has already been paid for.
"""

import json
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(REPO_ROOT, "desktop")
TAURI_CONF = os.path.join(DESKTOP, "src-tauri", "tauri.conf.json")
BUNDLE_CONF = os.path.join(DESKTOP, "src-tauri", "tauri.bundle.json")
CARGO_TOML = os.path.join(DESKTOP, "src-tauri", "Cargo.toml")
WORKFLOWS = os.path.join(REPO_ROOT, ".github", "workflows")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def tauri_conf():
    return json.loads(_read(TAURI_CONF))


def test_product_name_matches_cargo_bin_name(tauri_conf):
    """
    Not required by Tauri — the two names govern different artifacts. The macOS
    .app filename follows productName, while build-desktop-windows.yml greps
    for a hardcoded `mtga-draft-desktop.exe`, which follows the Cargo [[bin]]
    name. Pinned equal so a rename cannot satisfy one and break the other's
    artifact check.
    """
    cargo = _read(CARGO_TOML)
    match = re.search(r"\[\[bin\]\](?:[^\[]*?)name\s*=\s*\"([^\"]+)\"", cargo)
    assert match, "no [[bin]] name found in src-tauri/Cargo.toml"
    assert match.group(1) == tauri_conf["productName"]


def test_bundle_targets_are_macos_and_windows_only(tauri_conf):
    """
    Linux is not a supported platform: there is no build-desktop-linux.yml and
    no scripts/linux/. Leaving deb/rpm in the target list would make a local
    `tauri build` on any Linux host emit bundles nothing tests or ships.
    """
    bundle = json.loads(_read(BUNDLE_CONF))
    assert set(bundle["bundle"]["targets"]) == {"msi", "nsis", "app", "dmg"}


def test_bundle_overlay_ships_the_embedded_interpreter():
    """
    Without this resource mapping the bundle has no Python at all and the app
    dies at startup.
    """
    bundle = json.loads(_read(BUNDLE_CONF))
    assert bundle["bundle"]["active"] is True
    assert bundle["bundle"]["resources"]["pyembed/python"] == "./"


@pytest.mark.parametrize(
    "workflow",
    ["build-desktop-macos.yml", "build-desktop-windows.yml"],
)
def test_desktop_workflow_calls_the_shared_scripts(workflow):
    """
    Local and CI builds must not drift: the workflows invoke
    desktop/scripts/<os>/* rather than reimplementing the build inline.
    """
    text = _read(os.path.join(WORKFLOWS, workflow))
    platform = workflow.removeprefix("build-desktop-").removesuffix(".yml")
    assert f"desktop/scripts/{platform}/" in text.replace("\\", "/")


def test_upload_globs_match_the_bundle_profile():
    """
    `--profile bundle-release` puts artifacts under target/bundle-release/.
    A stale `target/release/` glob would fail only at the upload step, after a
    full build has already been paid for.
    """
    for workflow in (
        "build-desktop-macos.yml",
        "build-desktop-windows.yml",
    ):
        text = _read(os.path.join(WORKFLOWS, workflow))
        assert "desktop/target/bundle-release/bundle/" in text, workflow
        assert "if-no-files-found: error" in text, workflow
