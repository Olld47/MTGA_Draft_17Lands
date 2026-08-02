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

SCRIPTS = {
    "macos": os.path.join(DESKTOP, "scripts", "macos"),
    "windows": os.path.join(DESKTOP, "scripts", "windows"),
}
DOWNLOAD_SCRIPT = {
    "macos": os.path.join(SCRIPTS["macos"], "download-py.sh"),
    "windows": os.path.join(SCRIPTS["windows"], "download-py.ps1"),
}

# `tauri build` writes each bundle target to its own directory, and the name is
# not always the target's: "app" lands in bundle/macos/.
TARGET_DIRS = {"app": "macos", "dmg": "dmg", "msi": "msi", "nsis": "nsis"}

PUBLISH_WORKFLOW = os.path.join(WORKFLOWS, "publish-release.yml")
CHANGELOG = os.path.join(REPO_ROOT, "CHANGELOG.md")

# Every place the desktop version is written, as (path, regex, count). Seven
# files, eight literals: package-lock.json repeats it for the root package
# entry. Dependency version keys follow in the same files, so only the leading
# `count` matches belong to the app. desktop/Cargo.toml is absent on purpose —
# its [workspace.package] version is 0.1.0 and src-tauri does not inherit it.
DESKTOP_VERSION_SITES = [
    (os.path.join(DESKTOP, "package.json"), r'"version":\s*"([^"]+)"', 1),
    (os.path.join(DESKTOP, "package-lock.json"), r'"version":\s*"([^"]+)"', 2),
    (os.path.join(DESKTOP, "pyproject.toml"), r'(?m)^version\s*=\s*"([^"]+)"', 1),
    (
        os.path.join(DESKTOP, "src-tauri", "pyproject.toml"),
        r'(?m)^version\s*=\s*"([^"]+)"',
        1,
    ),
    (
        os.path.join(DESKTOP, "src-tauri", "Cargo.toml"),
        r'(?m)^version\s*=\s*"([^"]+)"',
        1,
    ),
    (
        os.path.join(DESKTOP, "Cargo.lock"),
        r'name = "mtga-draft-desktop"\nversion = "([^"]+)"',
        1,
    ),
    (TAURI_CONF, r'"version":\s*"([^"]+)"', 1),
]


def _upload_artifact_names(workflow_text):
    """Artifact names uploaded by jobs defined in one workflow file."""
    return set(
        re.findall(
            r"uses:\s*actions/upload-artifact@v\d+\s*\n\s*with:\s*\n\s*name:\s*(\S+)",
            workflow_text,
        )
    )


def _push_branches(workflow_text):
    """The `on: push: branches:` list of a workflow."""
    block = re.search(r"(?m)^\s+push:\n\s+branches:\n((?:\s+- .+\n)+)", workflow_text)
    assert block, "workflow has no push-branches trigger"
    return set(re.findall(r'(?m)- "?([^"\n]+?)"?\s*$', block.group(1)))


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


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_desktop_workflow_script_paths_exist(platform):
    """
    test_desktop_workflow_calls_the_shared_scripts only proves the directory is
    mentioned. Every script path the workflow actually invokes must resolve, or
    the leg dies at the step that calls it — after the toolchain, npm ci and the
    Rust cache have all been paid for.
    """
    text = _read(os.path.join(WORKFLOWS, f"build-desktop-{platform}.yml"))
    referenced = set(
        re.findall(r"desktop[\\/]scripts[\\/][\w\\/.-]+\.(?:sh|ps1)", text)
    )
    assert referenced, f"no script invocations found in build-desktop-{platform}.yml"
    for rel in referenced:
        path = os.path.join(REPO_ROOT, rel.replace("\\", os.sep).replace("/", os.sep))
        assert os.path.exists(path), f"{rel} is invoked but missing"


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_workflow_builds_rust_and_downloads_python_for_the_same_target(platform):
    """
    The Rust target triple and the python-build-standalone triple are written
    out separately, once for `dtolnay/rust-toolchain` and once as the argument
    to download-py. A mismatch links a binary of one architecture against an
    interpreter of another, and only fails deep into `tauri build`.
    """
    text = _read(os.path.join(WORKFLOWS, f"build-desktop-{platform}.yml"))
    rust_target = re.search(r"targets:\s*(\S+)", text)
    assert rust_target, "no rust-toolchain target declared"
    download = re.search(r"download-py\.(?:sh|ps1)\s+(\S+)", text)
    assert download, "download-py is called without an explicit target triple"
    assert download.group(1) == rust_target.group(1)


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_embedded_python_version_is_pinned_identically_across_platforms(platform):
    """
    Each download script carries its own PYTHON_VERSION/TAG literal. Nothing
    links them, so an update to one silently ships a macOS build and a Windows
    build running different interpreters — a class of bug that only appears as
    a behavioural difference between platforms, never as a build failure.
    """
    reference = _read(DOWNLOAD_SCRIPT["macos"])
    text = _read(DOWNLOAD_SCRIPT[platform])
    for field in ("PYTHON_VERSION", "TAG"):
        expected = re.search(rf"{field}\s*=\s*\"([\d.]+)\"", reference)
        actual = re.search(rf"{field}\s*=\s*\"([\d.]+)\"", text)
        assert actual, f"{field} not found in the {platform} download script"
        assert actual.group(1) == expected.group(1), field


def test_upload_globs_cover_every_configured_bundle_target():
    """
    The two workflows split one shared target list between them. An added
    target that no workflow globs is built and thrown away; a globbed directory
    no target produces trips `if-no-files-found: error` at the upload step,
    failing a build that otherwise succeeded.
    """
    targets = json.loads(_read(BUNDLE_CONF))["bundle"]["targets"]
    expected = {TARGET_DIRS[target] for target in targets}

    globbed = set()
    for workflow in ("build-desktop-macos.yml", "build-desktop-windows.yml"):
        text = _read(os.path.join(WORKFLOWS, workflow))
        globbed |= set(
            re.findall(r"desktop/target/bundle-release/bundle/(\w+)/", text)
        )
    assert globbed == expected


@pytest.mark.parametrize("script", ["download-py.ps1", "build.ps1"])
def test_windows_scripts_check_native_exit_codes(script):
    """
    PowerShell's $ErrorActionPreference = "Stop" does not apply to native
    executables, so a failed `uv pip install` leaves $LASTEXITCODE set and the
    script sails on to produce a bundle missing that package. The macOS scripts
    get this from `set -e`; the Windows ones must check by hand, and this leg
    has never been run against a real failure.
    """
    text = _read(os.path.join(SCRIPTS["windows"], script))
    native = re.findall(r"(?m)^\s*(?:[\w.-]+\.exe|npm)\b", text)
    assert native, f"no native invocations found in {script}"
    assert len(re.findall(r"\$LASTEXITCODE", text)) >= len(native)


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_desktop_workflows_are_reachable_without_the_gh_cli(platform):
    """
    workflow_dispatch alone requires the Actions web UI or `gh`. A push trigger
    on a dedicated branch namespace is what makes these legs runnable from a
    terminal without either; it is deliberately not a real branch, so a full
    Rust + numba build is never on the path of ordinary work.
    """
    text = _read(os.path.join(WORKFLOWS, f"build-desktop-{platform}.yml"))
    branches = re.findall(r"(?m)^\s+- \"?(ci/desktop[\w*-]*)\"?\s*$", text)
    assert branches, "no ci/desktop* push trigger"
    assert "workflow_dispatch:" in text


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


def test_desktop_version_is_consistent_across_manifests():
    """
    The desktop app carries its version in eight literals across seven files,
    and only tauri.conf.json reaches a user — it names the .dmg/.msi and fills
    Info.plist. The other seven exist to be consistent with it, so a stale one
    is invisible until someone reads it and believes it.

    Pinned to the topmost CHANGELOG heading rather than only to each other,
    because agreeing-but-stale is the failure that actually happened: the
    changelog reached v0.12 while all eight sat at 0.7.0 from v0.7, and CI
    published bundles named 0.7.0 five releases running. A manifests-only check
    passes happily through that.
    """
    heading = re.search(r"(?m)^## \[v(\d+)\.(\d+)(?:\.(\d+))?\]", _read(CHANGELOG))
    assert heading, "no '## [vX.Y]' heading found in CHANGELOG.md"
    major, minor, patch = heading.groups()
    expected = f"{major}.{minor}.{patch or 0}"

    for path, pattern, count in DESKTOP_VERSION_SITES:
        found = re.findall(pattern, _read(path))[:count]
        rel = os.path.relpath(path, REPO_ROOT)
        assert len(found) == count, f"{rel}: expected {count} version literals"
        for version in found:
            assert (
                version == expected
            ), f"{rel} says {version}, changelog says v{expected}"


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_desktop_workflows_build_on_the_release_branches(platform):
    """
    The desktop legs are the only thing that builds the bundles, and they are
    deliberately separate runs rather than jobs inside publish-release.yml
    (`continue-on-error` is not permitted on a reusable-workflow call, so a red
    desktop build would redden an otherwise-successful release).

    That separation is what makes this assertion necessary: nothing in
    publish-release.yml references these files, so if the trigger silently
    reverted to ci/desktop*-only, a release would go out with no desktop bundle
    built and no failure anywhere to say so.
    """
    branches = _push_branches(
        _read(os.path.join(WORKFLOWS, f"build-desktop-{platform}.yml"))
    )
    release_branches = _push_branches(_read(PUBLISH_WORKFLOW))
    assert release_branches <= branches, (
        f"build-desktop-{platform}.yml does not build on "
        f"{sorted(release_branches - branches)}"
    )


def test_release_artifacts_exclude_the_desktop_bundles():
    """
    The desktop bundles are unsigned and the .msi has never been launched, so
    they are built but must not be attached to a Release.

    The publish job's download step passes neither `name` nor `pattern` and sets
    `merge-multiple: true`, so it takes *every* artifact in its run and flattens
    them into one directory. Adding a desktop build job to this file would
    therefore attach the NSIS .exe silently, and the release-body generator —
    `next(f for f in files if f.endswith('.exe'))` — could name it in the
    Windows verification instructions.

    Asserted structurally rather than by emulating the glob: Python's fnmatch
    has no brace expansion, so a pattern-matching version of this test would
    return False for everything and pass vacuously.
    """
    publish = _read(PUBLISH_WORKFLOW)
    desktop_artifacts = set()
    for platform in ("macos", "windows"):
        desktop_artifacts |= _upload_artifact_names(
            _read(os.path.join(WORKFLOWS, f"build-desktop-{platform}.yml"))
        )
    assert desktop_artifacts, "the desktop workflows upload nothing"

    published = _upload_artifact_names(publish)
    assert published, "publish-release.yml uploads no artifacts"
    assert not (published & desktop_artifacts)

    for target in ("dmg", "msi", "nsis", "bundle-release"):
        assert target not in publish, f"publish-release.yml references {target}"
