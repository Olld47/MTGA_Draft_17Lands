"""bump_desktop_version.py

One-command desktop version bump. tauri.conf.json is the single source of
truth for the desktop series; this script rewrites every manifest literal and
the CHANGELOG heading from one input, so a release touches exactly one place.

The rewrite contract is pinned by tests/test_bump_desktop_version.py on fixture
strings, and the consistency guard tests/test_desktop_bundle_config.py imports
VERSION_SITES from here so the script and the test can never disagree about
which files carry the version.
"""

import argparse
import os
import re

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Every place the desktop version is written, as (path relative to REPO_ROOT,
# regex, count). Nine files, ten literals: desktop-version.lock is the CI
# anchor — the consistency guard reads it on every run, so a version bump that
# misses a site fails tests instead of shipping a mismatched bundle.
# package-lock.json repeats the version for the root package entry, and
# mtga_bridge/version.py is the literal the app-update check reads. Dependency
# version keys follow in the same files, so only the leading `count` matches
# belong to the app. desktop/Cargo.toml is absent on purpose — its
# [workspace.package] version is 0.1.0 and src-tauri does not inherit it.
VERSION_SITES = [
    ("desktop-version.lock", r'(?m)^(\d+\.\d+(?:\.\d+)?)$', 1),
    (os.path.join("desktop", "package.json"), r'"version":\s*"([^"]+)"', 1),
    (os.path.join("desktop", "package-lock.json"), r'"version":\s*"([^"]+)"', 2),
    (os.path.join("desktop", "pyproject.toml"), r'(?m)^version\s*=\s*"([^"]+)"', 1),
    (
        os.path.join("desktop", "src-tauri", "pyproject.toml"),
        r'(?m)^version\s*=\s*"([^"]+)"',
        1,
    ),
    (
        os.path.join("desktop", "src-tauri", "Cargo.toml"),
        r'(?m)^version\s*=\s*"([^"]+)"',
        1,
    ),
    (
        os.path.join("desktop", "Cargo.lock"),
        r'name = "mtga-draft-desktop"\nversion = "([^"]+)"',
        1,
    ),
    (
        os.path.join("desktop", "src-tauri", "tauri.conf.json"),
        r'"version":\s*"([^"]+)"',
        1,
    ),
    (
        os.path.join(
            "desktop",
            "src-tauri",
            "src-python",
            "mtga_bridge",
            "version.py",
        ),
        r'DESKTOP_VERSION\s*=\s*"([^"]+)"',
        1,
    ),
]

CHANGELOG = os.path.join(REPO_ROOT, "CHANGELOG.md")

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
_CHANGELOG_HEADING_RE = re.compile(r"(?m)^## \[v\d+\.\d+(?:\.\d+)?\]")


def _validate_version(version):
    """Accept 'X.Y' or 'X.Y.Z'; return the normalized 3-part form."""
    match = _VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(f"invalid desktop version: {version!r} (use X.Y or X.Y.Z)")
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{patch or 0}"


def rewrite_versions(content, pattern, new_version, count):
    """Rewrite the first `count` occurrences of `pattern` in `content` to
    `new_version`, replacing only the captured group's span. Returns
    (content, replaced_count) so callers can detect silent under-replacement."""

    def _splice(match):
        a, b = match.span(1)
        return (
            match.group(0)[: a - match.start(0)]
            + new_version
            + match.group(0)[b - match.start(0) :]
        )

    return re.subn(pattern, _splice, content, count=count)


def bump_changelog(content, new_version):
    """Rewrite the topmost CHANGELOG heading to the 2-part form (0.40.0 -> v0.40)."""
    short = ".".join(new_version.split(".")[:2])
    out, n = _CHANGELOG_HEADING_RE.subn(f"## [v{short}]", content, count=1)
    if n == 0:
        raise ValueError("no '## [vX.Y]' heading found in CHANGELOG.md")
    return out


def bump_all(new_version):
    """Rewrite every VERSION_SITES literal and the CHANGELOG heading to
    `new_version`. Raises if any site holds fewer matches than its count."""
    version = _validate_version(new_version)
    for rel, pattern, count in VERSION_SITES:
        path = rel if os.path.isabs(rel) else os.path.join(REPO_ROOT, rel)
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        content, replaced = rewrite_versions(content, pattern, version, count)
        if replaced != count:
            raise ValueError(
                f"{rel}: expected {count} version literal(s), replaced {replaced}"
            )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    with open(CHANGELOG, encoding="utf-8") as handle:
        changelog = handle.read()
    with open(CHANGELOG, "w", encoding="utf-8") as handle:
        handle.write(bump_changelog(changelog, version))


def main():
    parser = argparse.ArgumentParser(
        description="Bump the desktop app version across all manifests + CHANGELOG."
    )
    parser.add_argument("version", help="new version, e.g. 0.40.0 (X.Y or X.Y.Z)")
    args = parser.parse_args()
    new_version = _validate_version(args.version)
    bump_all(new_version)
    print(
        f"SUCCESS: desktop version bumped to {new_version} "
        "across all manifests + CHANGELOG"
    )


if __name__ == "__main__":
    main()
