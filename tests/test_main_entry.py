"""
tests/test_main_entry.py
Entry-point dispatch: --ui / default_ui routing in main.py.
"""

import logging
import os
import subprocess
import sys

import pytest

import main as entry


# --- resolve_target_ui -------------------------------------------------------


def test_resolve_target_ui_explicit_cli_wins():
    assert entry.resolve_target_ui("desktop", "tkinter") == "desktop"
    assert entry.resolve_target_ui("tkinter", "desktop") == "tkinter"


def test_resolve_target_ui_auto_reads_configured():
    assert entry.resolve_target_ui("auto", "tkinter") == "tkinter"
    assert entry.resolve_target_ui("auto", "desktop") == "desktop"


def test_resolve_target_ui_invalid_falls_back():
    from src import constants

    assert entry.resolve_target_ui("browser", "tkinter") == "tkinter"
    assert entry.resolve_target_ui("auto", "browser") == constants.DEFAULT_UI_DEFAULT


# --- find_desktop_launcher ---------------------------------------------------


def test_find_desktop_launcher_prefers_env_var(monkeypatch):
    env_bin = "/opt/mtga/mtga-draft-desktop"
    monkeypatch.setenv("MTGA_DRAFT_DESKTOP", env_bin)
    monkeypatch.setattr(os.path, "isfile", lambda p: p == env_bin)
    monkeypatch.setattr(os, "access", lambda p, m: p == env_bin)
    assert entry.find_desktop_launcher() == env_bin


def test_find_desktop_launcher_env_app_dir_probes_inner_binary(monkeypatch):
    if sys.platform != "darwin":
        pytest.skip("inner .app probe is darwin-only")
    app_dir = "/Applications/mtga-draft-desktop.app"
    inner = os.path.join(app_dir, "Contents", "MacOS", "mtga-draft-desktop")
    monkeypatch.setenv("MTGA_DRAFT_DESKTOP", app_dir)
    monkeypatch.setattr(os.path, "isdir", lambda p: p == app_dir)
    monkeypatch.setattr(os.path, "isfile", lambda p: p == inner)
    monkeypatch.setattr(os, "access", lambda p, m: p == inner)
    assert entry.find_desktop_launcher() == inner


def test_find_desktop_launcher_first_built_binary_wins(monkeypatch):
    from src import constants

    monkeypatch.delenv("MTGA_DRAFT_DESKTOP", raising=False)
    exe = ".exe" if sys.platform == "win32" else ""
    release_bin = os.path.join(
        constants.BASE_DIR, "desktop", "target", "release", f"mtga-draft-desktop{exe}"
    )
    monkeypatch.setattr(os.path, "isfile", lambda p: p == release_bin)
    monkeypatch.setattr(os, "access", lambda p, m: p == release_bin)
    assert entry.find_desktop_launcher() == release_bin


def test_find_desktop_launcher_none_when_nothing_built(monkeypatch):
    monkeypatch.delenv("MTGA_DRAFT_DESKTOP", raising=False)
    monkeypatch.setattr(os.path, "isfile", lambda p: False)
    monkeypatch.setattr(os, "access", lambda p, m: False)
    assert entry.find_desktop_launcher() is None


# --- launch_desktop ----------------------------------------------------------


def test_launch_desktop_forwards_file_and_data_and_exits_zero(monkeypatch):
    captured = {}

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs

    monkeypatch.setattr(entry.subprocess, "Popen", fake_popen)
    with pytest.raises(SystemExit) as exc:
        entry.launch_desktop(
            "/opt/bin", file="/logs/Player.log", data="/mtga/data"
        )
    assert exc.value.code == 0
    assert captured["argv"] == [
        "/opt/bin",
        "-f",
        "/logs/Player.log",
        "-d",
        "/mtga/data",
    ]
    kwargs = captured["kwargs"]
    assert kwargs.get("stdout") == subprocess.DEVNULL
    assert kwargs.get("stderr") == subprocess.DEVNULL
    if sys.platform == "win32":
        assert "creationflags" in kwargs
    else:
        assert kwargs.get("start_new_session") is True


def test_launch_desktop_minimal_argv(monkeypatch):
    captured = {}

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv

    monkeypatch.setattr(entry.subprocess, "Popen", fake_popen)
    with pytest.raises(SystemExit) as exc:
        entry.launch_desktop("/opt/bin")
    assert exc.value.code == 0
    assert captured["argv"] == ["/opt/bin"]


# --- dispatch_ui -------------------------------------------------------------


def test_dispatch_ui_launches_desktop_and_exits_zero(monkeypatch):
    captured = {}
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: "/fake/bin")

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv

    monkeypatch.setattr(entry.subprocess, "Popen", fake_popen)
    with pytest.raises(SystemExit) as exc:
        entry.dispatch_ui("auto", "desktop", file="/logs/Player.log")
    assert exc.value.code == 0
    assert captured["argv"] == ["/fake/bin", "-f", "/logs/Player.log"]


def test_dispatch_ui_explicit_desktop_without_build_exits_two(monkeypatch, capsys):
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: None)
    with pytest.raises(SystemExit) as exc:
        entry.dispatch_ui("desktop", "desktop")
    assert exc.value.code == 2
    assert "No desktop build found" in capsys.readouterr().out


def test_dispatch_ui_auto_desktop_without_build_falls_back(monkeypatch, caplog):
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: None)
    with caplog.at_level(logging.WARNING):
        assert entry.dispatch_ui("auto", "desktop") is None
    assert any("falling back to the tkinter UI" in r.message for r in caplog.records)


def test_dispatch_ui_tkinter_never_probes(monkeypatch):
    def boom():
        raise AssertionError("find_desktop_launcher must not be called")

    monkeypatch.setattr(entry, "find_desktop_launcher", boom)
    assert entry.dispatch_ui("tkinter", "desktop") is None


# --- main() wiring -----------------------------------------------------------


def test_main_version_exits_before_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(entry.sys, "argv", ["main.py", "--version"])
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 0
    assert "v" in capsys.readouterr().out


def test_main_explicit_desktop_without_build_exits_two(monkeypatch, capsys):
    from src.configuration import Configuration

    monkeypatch.setattr(entry.sys, "argv", ["main.py", "--ui", "desktop"])
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    monkeypatch.setattr(entry, "read_configuration", lambda: (Configuration(), False))
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: None)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 2
    assert "No desktop build found" in capsys.readouterr().out
