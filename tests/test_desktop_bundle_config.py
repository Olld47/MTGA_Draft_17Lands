"""
tests/test_desktop_bundle_config.py

Guards the desktop bundling contract that cannot be checked from macOS.

The load-bearing fact: tauri-bundler places deb/rpm resources at
`/usr/lib/<productName>` **verbatim** — it does not slugify, and
`tauri::utils::platform::resource_dir()` resolves the same name at runtime.
The Linux build script bakes that path into the binary's rpath so it can find
the embedded `libpython3.x.so`. If the two disagree the .deb dies at the
dynamic linker, before any Python runs, which no unit test would otherwise see.

These assertions are cheap; the failure they prevent costs a full CI build to
discover.
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
LINUX_BUILD = os.path.join(DESKTOP, "scripts", "linux", "build.sh")
WORKFLOWS = os.path.join(REPO_ROOT, ".github", "workflows")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def tauri_conf():
    return json.loads(_read(TAURI_CONF))


@pytest.fixture(scope="module")
def linux_build():
    return _read(LINUX_BUILD)


def test_product_name_has_no_whitespace(tauri_conf):
    """
    RUSTFLAGS is a space-separated string, so a space inside the rpath would
    truncate it mid-path and the link-arg would silently point somewhere else.
    Keeping productName whitespace-free is what makes the plain (non-encoded)
    RUSTFLAGS in scripts/linux/build.sh safe.
    """
    product_name = tauri_conf["productName"]
    assert product_name == product_name.strip()
    assert not re.search(r"\s", product_name), (
        f"productName {product_name!r} contains whitespace; the deb resource "
        "dir is /usr/lib/<productName> verbatim and scripts/linux/build.sh "
        "interpolates it into space-separated RUSTFLAGS"
    )


def test_product_name_matches_cargo_bin_name(tauri_conf):
    """
    Not required by Tauri — the deb resource dir follows productName while
    /usr/bin/<name> follows the Cargo [[bin]] name. Pinned equal anyway so the
    upload globs and the rpath check in build-desktop-linux.yml can assume one
    name, and so a rename cannot leave half the pipeline behind.
    """
    cargo = _read(CARGO_TOML)
    match = re.search(r"\[\[bin\]\](?:[^\[]*?)name\s*=\s*\"([^\"]+)\"", cargo)
    assert match, "no [[bin]] name found in src-tauri/Cargo.toml"
    assert match.group(1) == tauri_conf["productName"]


def test_linux_rpath_derives_from_product_name(linux_build):
    """
    The script must *read* productName out of tauri.conf.json rather than
    hardcode it — a duplicated literal is exactly how this broke before, when
    the rpath said `mtga-draft-desktop` and the bundler wrote
    `/usr/lib/MTGA Draft Tool/`.
    """
    assert "tauri.conf.json" in linux_build, (
        "scripts/linux/build.sh must read productName from tauri.conf.json"
    )
    assert re.search(r'rpath,\\\$ORIGIN/\.\./lib/\$PRODUCT_NAME/lib', linux_build), (
        "the rpath must interpolate $PRODUCT_NAME, not a hardcoded name"
    )


def test_linux_rpath_target_is_where_the_bundler_writes_resources(
    tauri_conf, linux_build
):
    """
    End-to-end on the string level: expand the script's rpath by hand and
    assert it equals the directory tauri-bundler will create.
    """
    product_name = tauri_conf["productName"]
    match = re.search(r"rpath,\\\$ORIGIN/(\S+)", linux_build)
    assert match, "no rpath link-arg in scripts/linux/build.sh"

    expanded = match.group(1).replace("$PRODUCT_NAME", product_name)
    assert expanded == f"../lib/{product_name}/lib"


def test_bundle_overlay_ships_the_embedded_interpreter():
    """
    Without this resource mapping the bundle has no Python at all and the
    rpath points at an empty directory.
    """
    bundle = json.loads(_read(BUNDLE_CONF))
    assert bundle["bundle"]["active"] is True
    assert bundle["bundle"]["resources"]["pyembed/python"] == "./"


@pytest.mark.parametrize(
    "workflow",
    ["build-desktop-macos.yml", "build-desktop-linux.yml", "build-desktop-windows.yml"],
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
        "build-desktop-linux.yml",
        "build-desktop-windows.yml",
    ):
        text = _read(os.path.join(WORKFLOWS, workflow))
        assert "desktop/target/bundle-release/bundle/" in text, workflow
        assert "if-no-files-found: error" in text, workflow
