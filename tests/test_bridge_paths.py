"""
tests/test_bridge_paths.py
Covers the base-directory resolution shared by the desktop entry points
(src/app_paths.py) and the dev-vs-bundled dispatch in
mtga_bridge.paths. Both are import-time load-bearing: constants.BASE_DIR is
read at module import by nearly every module, so a regression here silently
relocates Sets/, Logs/, Temp/ and config.json.
"""

import os
import subprocess
import sys
from unittest.mock import patch

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

from src import app_paths
from mtga_bridge import paths

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def restore_cwd():
    original = os.getcwd()
    yield
    os.chdir(original)


@pytest.fixture
def no_base_dir_env(monkeypatch):
    # setenv-then-delenv so monkeypatch records a restore entry even when the
    # var was absent — ensure_runtime_paths() sets it and would otherwise leak.
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, "")
    monkeypatch.delenv(app_paths.BASE_DIR_ENV_VAR)


# --- user_data_dir ---------------------------------------------------------


def test_user_data_dir_macos():
    with patch.object(sys, "platform", "darwin"):
        expected = os.path.expanduser(
            "~/Library/Application Support/MTGA_Draft_Tool"
        )
        assert app_paths.user_data_dir() == expected


def test_user_data_dir_linux():
    with patch.object(sys, "platform", "linux"):
        assert app_paths.user_data_dir() == os.path.expanduser(
            "~/.config/MTGA_Draft_Tool"
        )


def test_user_data_dir_windows_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", os.path.join("C:\\Users", "tester", "AppData"))
    with patch.object(sys, "platform", "win32"):
        assert app_paths.user_data_dir() == os.path.join(
            "C:\\Users", "tester", "AppData", "MTGA_Draft_Tool"
        )


def test_user_data_dir_windows_falls_back_to_home(monkeypatch):
    """A Windows session with no APPDATA must still resolve somewhere writable."""
    monkeypatch.delenv("APPDATA", raising=False)
    with patch.object(sys, "platform", "win32"):
        assert app_paths.user_data_dir() == os.path.join(
            os.path.expanduser("~"), "MTGA_Draft_Tool"
        )


# --- resolve_base_dir ------------------------------------------------------


def test_resolve_base_dir_source_checkout_uses_cwd(
    tmp_path, restore_cwd, no_base_dir_env
):
    os.chdir(tmp_path)
    assert os.path.realpath(app_paths.resolve_base_dir()) == os.path.realpath(
        str(tmp_path)
    )


def test_resolve_base_dir_frozen_uses_user_data_dir(tmp_path, no_base_dir_env):
    target = str(tmp_path / "frozen_home")
    with patch.object(sys, "frozen", True, create=True), patch.object(
        app_paths, "user_data_dir", return_value=target
    ):
        assert app_paths.resolve_base_dir() == target
    assert os.path.isdir(target)


def test_resolve_base_dir_env_override_beats_frozen(tmp_path, monkeypatch):
    """The bundled pytauri app opts in via the env var; sys.frozen is never set."""
    target = str(tmp_path / "override")
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, target)
    with patch.object(sys, "frozen", True, create=True):
        assert app_paths.resolve_base_dir() == target
    assert os.path.isdir(target)


def test_resolve_base_dir_env_override_beats_cwd(
    tmp_path, monkeypatch, restore_cwd
):
    target = str(tmp_path / "override")
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, target)
    os.chdir(tmp_path)
    assert app_paths.resolve_base_dir() == target


def test_resolve_base_dir_creates_missing_directory(tmp_path, monkeypatch):
    target = str(tmp_path / "deep" / "nested")
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, target)
    assert app_paths.resolve_base_dir() == target
    assert os.path.isdir(target)


# --- constants / logger delegate to app_paths ------------------------------


def test_constants_base_dir_honors_env_override(tmp_path):
    """BASE_DIR is computed when src.constants is first imported; a fresh
    process that sets MTGA_DRAFT_BASE_DIR before importing must resolve every
    derived folder under it (this is how the bundled pytauri app opts in)."""
    target = str(tmp_path / "relocated")
    script = (
        "import os, sys\n"
        f"sys.path.insert(0, {REPO_ROOT!r})\n"
        f"os.environ['{app_paths.BASE_DIR_ENV_VAR}'] = {target!r}\n"
        "from src import constants\n"
        "print(constants.BASE_DIR)\n"
        "print(constants.SETS_FOLDER)\n"
        "print(constants.TEMP_FOLDER)\n"
        "print(constants.DRAFT_LOG_FOLDER)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    assert lines[0] == target
    assert lines[1] == os.path.join(target, "Sets")
    assert lines[2] == os.path.join(target, "Temp")
    assert lines[3] == os.path.join(target, "Logs")


def test_logger_debug_folder_tracks_base_dir():
    """logger.py and constants.py must not fork their base-dir logic again."""
    from src import logger

    assert logger.DEBUG_LOG_FOLDER == os.path.join(
        app_paths.resolve_base_dir(), "Debug"
    )


# --- find_repo_root --------------------------------------------------------


def test_find_repo_root_locates_checkout():
    assert os.path.realpath(paths.find_repo_root()) == os.path.realpath(REPO_ROOT)


def test_find_repo_root_returns_none_when_bundled(tmp_path):
    """Real bundle layout: `src` is installed INTO site-packages next to
    mtga_bridge (build.sh installs the repo-root package), but site-packages
    has no poetry project markers. `src/constants` alone must NOT classify it
    as a source checkout — that bug relocated Sets/Logs/Temp/config.json
    inside the .app bundle, wiping them on update."""
    sp = tmp_path / "lib" / "python3.13" / "site-packages"
    (sp / "mtga_bridge").mkdir(parents=True)
    (sp / "src" / "constants").mkdir(parents=True)
    (sp / "pydantic-2.13.4.dist-info").mkdir()
    (sp / "README.txt").write_text("This is a Python package directory\n")
    with patch.object(paths, "__file__", str(sp / "mtga_bridge" / "paths.py")):
        assert paths.find_repo_root() is None


def test_find_repo_root_requires_project_markers(tmp_path):
    """A directory with `src/constants` but missing a project marker is not a
    checkout — regression guard for the marker requirements."""
    fake = tmp_path / "src" / "constants"
    fake.mkdir(parents=True)
    with patch.object(paths, "__file__", str(tmp_path / "mtga_bridge" / "paths.py")):
        assert paths.find_repo_root() is None

    (tmp_path / "pyproject.toml").write_text("[project]\n")
    with patch.object(paths, "__file__", str(tmp_path / "mtga_bridge" / "paths.py")):
        assert paths.find_repo_root() is None

    (tmp_path / "main.py").write_text("")
    with patch.object(paths, "__file__", str(tmp_path / "mtga_bridge" / "paths.py")):
        assert os.path.realpath(paths.find_repo_root()) == os.path.realpath(
            str(tmp_path)
        )


def test_find_repo_root_follows_symlinked_editable_install(tmp_path):
    """An editable install may symlink `mtga_bridge` into site-packages while
    the rest of the package tree stays in the checkout. The walk must resolve
    the link back to the real checkout root — starting from the link location
    alone misses src/constants + markers and silently falls back to the
    per-user data dir (config/data "reset" after an update)."""
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "constants").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\n")
    (repo_root / "main.py").write_text("")
    # Source tree as installed editable: <checkout>/desktop/src-tauri/src-python/mtga_bridge
    pkg = repo_root / "desktop" / "src-tauri" / "src-python" / "mtga_bridge"
    pkg.mkdir(parents=True)
    # venv OUTSIDE the checkout, linked back into it
    sp = tmp_path / "venv" / "lib" / "site-packages"
    sp.mkdir(parents=True)
    (sp / "mtga_bridge").symlink_to(pkg, target_is_directory=True)

    with patch.object(paths, "__file__", str(sp / "mtga_bridge" / "paths.py")):
        assert os.path.realpath(paths.find_repo_root()) == os.path.realpath(
            str(repo_root)
        )


# --- ensure_runtime_paths --------------------------------------------------


def test_ensure_runtime_paths_dev_mode_chdirs_to_repo(restore_cwd, tmp_path):
    os.chdir(tmp_path)
    root = paths.ensure_runtime_paths()
    assert os.path.realpath(root) == os.path.realpath(REPO_ROOT)
    assert os.path.realpath(os.getcwd()) == os.path.realpath(REPO_ROOT)
    assert REPO_ROOT in sys.path


def test_ensure_runtime_paths_bundled_uses_user_data_dir(
    tmp_path, no_base_dir_env, restore_cwd
):
    target = str(tmp_path / "bundled_home")

    with patch.object(paths, "find_repo_root", return_value=None), patch.object(
        app_paths, "user_data_dir", return_value=target
    ):
        root = paths.ensure_runtime_paths()

    assert root == target
    assert os.environ[app_paths.BASE_DIR_ENV_VAR] == target
    assert os.path.realpath(os.getcwd()) == os.path.realpath(target)


def test_ensure_runtime_paths_bundled_respects_existing_env(
    tmp_path, monkeypatch, restore_cwd
):
    """A user-set MTGA_DRAFT_BASE_DIR must not be clobbered by the default."""
    target = str(tmp_path / "user_choice")
    os.makedirs(target)
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, target)

    with patch.object(paths, "find_repo_root", return_value=None), patch.object(
        app_paths, "user_data_dir", return_value=str(tmp_path / "default")
    ):
        root = paths.ensure_runtime_paths()

    assert root == target
    assert not os.path.exists(str(tmp_path / "default"))
