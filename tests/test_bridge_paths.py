"""
tests/test_bridge_paths.py
Covers the base-directory resolution shared by the tkinter and pytauri entry
points (src/app_paths.py) and the dev-vs-bundled dispatch in
mtga_bridge.paths. Both are import-time load-bearing: constants.BASE_DIR is
read at module import by nearly every module, so a regression here silently
relocates Sets/, Logs/, Temp/ and config.json.
"""

import importlib
import os
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


def test_constants_base_dir_honors_env_override(tmp_path, monkeypatch):
    """constants.BASE_DIR is computed at import; reimporting under the override
    must relocate every derived folder with it."""
    target = str(tmp_path / "relocated")
    monkeypatch.setenv(app_paths.BASE_DIR_ENV_VAR, target)

    import src.constants as constants

    reloaded = importlib.reload(constants)
    try:
        assert reloaded.BASE_DIR == target
        assert reloaded.SETS_FOLDER == os.path.join(target, "Sets")
        assert reloaded.TEMP_FOLDER == os.path.join(target, "Temp")
        assert reloaded.DRAFT_LOG_FOLDER == os.path.join(target, "Logs")
    finally:
        monkeypatch.delenv(app_paths.BASE_DIR_ENV_VAR, raising=False)
        importlib.reload(reloaded)


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
    """Walking up from an embedded site-packages never reaches src/constants.py."""
    fake = tmp_path / "lib" / "python3.13" / "site-packages" / "mtga_bridge"
    fake.mkdir(parents=True)
    with patch.object(paths, "__file__", str(fake / "paths.py")):
        assert paths.find_repo_root() is None


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
