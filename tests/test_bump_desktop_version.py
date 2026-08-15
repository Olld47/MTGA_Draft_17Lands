"""
tests/test_bump_desktop_version.py

Tests the one-command desktop version bump (bump_desktop_version.py). The script
is the single place that knows the 9 files / 10 literals of the desktop version;
this module pins its rewrite contract on fixture strings (not real files), and
runs bump_all once against a throwaway temp dir.

Every rewrite is checked by the repo's mutation convention: the splice repl
must change the captured version group and nothing else, and bump_all must
raise when a site didn't actually get replaced (the "agrees-but-stale" failure
mode this script exists to kill).
"""

import os

import pytest

import bump_desktop_version as bdv


# --- _validate_version ------------------------------------------------------


def test_validate_version_accepts_three_part():
    assert bdv._validate_version("0.40.0") == "0.40.0"


def test_validate_version_pads_two_part_to_three():
    assert bdv._validate_version("0.40") == "0.40.0"


@pytest.mark.parametrize(
    "bad", ["banana", "v0.40", "0.40.0.1", "0.x.0", ""]
)
def test_validate_version_rejects_garbage(bad):
    with pytest.raises(ValueError):
        bdv._validate_version(bad)


# --- rewrite_versions: per-site splice --------------------------------------

PACKAGE_JSON = (
    '{\n'
    '  "name": "mtga-draft-desktop",\n'
    '  "version": "0.39.0",\n'
    '  "scripts": { "build": "vite build" }\n'
    '}\n'
)


def test_package_json_first_version_rewritten():
    out, n = bdv.rewrite_versions(PACKAGE_JSON, r'"version":\s*"([^"]+)"', "0.40.0", 1)
    assert n == 1
    assert '"version": "0.40.0"' in out
    assert '"name": "mtga-draft-desktop"' in out


PACKAGE_LOCK = (
    '{\n'
    '  "name": "mtga-draft-desktop",\n'
    '  "version": "0.39.0",\n'
    '  "packages": { "": { "version": "0.39.0" } },\n'
    '  "dependencies": { "react": { "version": "18.3.1" } }\n'
    '}\n'
)


def test_package_lock_first_two_versions_rewritten_only():
    out, n = bdv.rewrite_versions(PACKAGE_LOCK, r'"version":\s*"([^"]+)"', "0.40.0", 2)
    assert n == 2
    # root + packages[""] entries are the app's; the dependency must survive.
    assert out.count('"0.40.0"') == 2
    assert '"version": "18.3.1"' in out


PYPROJECT = 'name = "mtga-draft-desktop"\nversion = "0.39.0"\n'


def test_pyproject_line_anchored_version_rewritten():
    out, n = bdv.rewrite_versions(PYPROJECT, r'(?m)^version\s*=\s*"([^"]+)"', "0.40.0", 1)
    assert n == 1
    assert 'version = "0.40.0"' in out


CARGO_TOML = (
    '[package]\n'
    'name = "mtga-draft-desktop"\n'
    'version = "0.39.0"\n'
    '\n'
    '[dependencies]\n'
    'tauri = { version = "2", features = [] }\n'
)


def test_cargo_toml_package_version_not_dependency_versions():
    out, n = bdv.rewrite_versions(CARGO_TOML, r'(?m)^version\s*=\s*"([^"]+)"', "0.40.0", 1)
    assert n == 1
    assert 'version = "0.40.0"' in out
    assert 'tauri = { version = "2", features = [] }' in out


CARGO_LOCK = (
    '[[package]]\n'
    'name = "mtga-draft-desktop"\n'
    'version = "0.39.0"\n'
)


def test_cargo_lock_two_line_pattern_rewritten():
    pattern = r'name = "mtga-draft-desktop"\nversion = "([^"]+)"'
    out, n = bdv.rewrite_versions(CARGO_LOCK, pattern, "0.40.0", 1)
    assert n == 1
    assert 'name = "mtga-draft-desktop"\nversion = "0.40.0"' in out


TAURI_CONF = '{\n  "productName": "mtga-draft-desktop",\n  "version": "0.39.0"\n}\n'


def test_tauri_conf_version_rewritten():
    out, n = bdv.rewrite_versions(TAURI_CONF, r'"version":\s*"([^"]+)"', "0.40.0", 1)
    assert n == 1
    assert '"version": "0.40.0"' in out


VERSION_PY = '"""doc"""\n\nDESKTOP_VERSION = "0.39.0"\n'


def test_version_py_desktop_version_rewritten():
    out, n = bdv.rewrite_versions(VERSION_PY, r'DESKTOP_VERSION\s*=\s*"([^"]+)"', "0.40.0", 1)
    assert n == 1
    assert 'DESKTOP_VERSION = "0.40.0"' in out


def test_rewrite_under_replacement_is_countable():
    # A site whose content holds fewer matches than `count` must report it, so
    # bump_all can raise instead of silently shipping a stale literal.
    out, n = bdv.rewrite_versions(VERSION_PY, r'DESKTOP_VERSION\s*=\s*"([^"]+)"', "0.40.0", 2)
    assert n == 1


# --- bump_changelog ---------------------------------------------------------


CHANGELOG = "# Changelog\n\n## [v0.39] — something\n\nbody\n"


def test_bump_changelog_rewrites_heading_to_two_part():
    out = bdv.bump_changelog(CHANGELOG, "0.40.0")
    assert "## [v0.40]" in out
    assert "# Changelog" in out


def test_bump_changelog_raises_without_heading():
    with pytest.raises(ValueError):
        bdv.bump_changelog("# Changelog\n\nno heading here\n", "0.40.0")


# --- VERSION_SITES structure ------------------------------------------------


def test_version_sites_shape():
    assert len(bdv.VERSION_SITES) == 9
    assert sum(count for _, _, count in bdv.VERSION_SITES) == 10
    for rel, pattern, count in bdv.VERSION_SITES:
        assert not os.path.isabs(rel), f"{rel} must be repo-root-relative"
        assert count in (1, 2)
        assert pattern


# --- bump_all end-to-end against a temp dir ---------------------------------


def test_bump_all_rewrites_every_site_and_changelog(tmp_path, monkeypatch):
    sites = [
        ("package.json", r'"version":\s*"([^"]+)"', 1),
        ("package-lock.json", r'"version":\s*"([^"]+)"', 2),
        ("pyproject.toml", r'(?m)^version\s*=\s*"([^"]+)"', 1),
        ("Cargo.lock", r'name = "mtga-draft-desktop"\nversion = "([^"]+)"', 1),
        ("tauri.conf.json", r'"version":\s*"([^"]+)"', 1),
        ("version.py", r'DESKTOP_VERSION\s*=\s*"([^"]+)"', 1),
    ]
    contents = {
        "package.json": PACKAGE_JSON,
        "package-lock.json": PACKAGE_LOCK,
        "pyproject.toml": PYPROJECT,
        "Cargo.lock": CARGO_LOCK,
        "tauri.conf.json": TAURI_CONF,
        "version.py": VERSION_PY,
    }
    tmp_sites = []
    for rel, pattern, count in sites:
        path = tmp_path / rel
        path.write_text(contents[rel], encoding="utf-8")
        tmp_sites.append((str(path), pattern, count))

    monkeypatch.setattr(bdv, "VERSION_SITES", tmp_sites)
    monkeypatch.setattr(bdv, "CHANGELOG", str(tmp_path / "CHANGELOG.md"))
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")

    bdv.bump_all("0.40.0")

    for rel, _, _ in sites:
        text = (tmp_path / rel).read_text(encoding="utf-8")
        assert text.count("0.39.0") == 0, f"{rel} still holds the old version"
    assert "## [v0.40]" in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")


def test_bump_all_raises_when_a_site_never_replaces(tmp_path, monkeypatch):
    # A site whose content holds no version at all must fail loudly, not bump
    # the other sites and leave one stale.
    path = tmp_path / "version.py"
    path.write_text("DESKTOP_VERSION = None  # already gone\n")

    monkeypatch.setattr(
        bdv, "VERSION_SITES", [(str(path), r'DESKTOP_VERSION\s*=\s*"([^"]+)"', 1)]
    )

    with pytest.raises(ValueError):
        bdv.bump_all("0.40.0")
