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
from PIL import Image

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


def test_configured_icons_exist_at_their_declared_sizes(tauri_conf):
    """
    tauri.conf.json names icon paths but nothing validates them until a bundle
    build: a missing file fails `tauri build`, and a wrongly-sized PNG is worse
    still — it bundles silently and only looks wrong on a user's dock. The
    declared size is the filename, so it can be checked directly.
    """
    icon_root = os.path.join(DESKTOP, "src-tauri")
    declared = tauri_conf["bundle"]["icon"]
    assert declared, "no icons declared in tauri.conf.json"

    for rel in declared:
        path = os.path.join(icon_root, rel.replace("/", os.sep))
        assert os.path.exists(path), f"{rel} is declared but missing"

        match = re.fullmatch(r"(\d+)x\1(?:@(\d+)x)?\.png", os.path.basename(rel))
        if match:
            expected = int(match.group(1)) * int(match.group(2) or 1)
            with Image.open(path) as img:
                assert img.size == (expected, expected), rel


def test_icons_are_not_the_tauri_template_defaults():
    """
    The template ships a cyan/yellow pytauri logo. Shipping it would brand the
    release as a scaffold; the swap is easy to lose in a regenerate-icons step,
    and nothing else in CI looks at pixels. Sampled rather than hashed so the
    artwork can be retouched without editing this test.
    """
    path = os.path.join(DESKTOP, "src-tauri", "icons", "icon.png")
    with Image.open(path) as img:
        colors = img.convert("RGB").resize((16, 16), Image.BOX).getcolors(256)

    template_cyan = (36, 200, 219)
    assert not any(
        all(abs(channel - ref) < 30 for channel, ref in zip(color, template_cyan))
        for _, color in colors
    ), "icon.png still contains the pytauri template cyan"
