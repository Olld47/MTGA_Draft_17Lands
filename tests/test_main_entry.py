"""
tests/test_main_entry.py
Entry-point launcher behavior: desktop binary resolution, `-f/-d` forwarding,
and exit codes in main.py. There is no UI routing anymore — the desktop app
is the only client, so the launcher never consults default_ui and never falls
through to a fallback UI.
"""

import os
import subprocess
import sys

import pytest

import main as entry


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


# --- main() wiring -----------------------------------------------------------


def test_main_version_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(entry.sys, "argv", ["main.py", "--version"])
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 0
    assert "v" in capsys.readouterr().out


def test_main_launches_desktop_and_forwards_args(monkeypatch):
    from src.configuration import Configuration

    captured = {}
    monkeypatch.setattr(
        entry.sys,
        "argv",
        ["main.py", "-f", "/logs/Player.log", "-d", "/mtga/data"],
    )
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    monkeypatch.setattr(entry, "read_configuration", lambda: (Configuration(), False))
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: "/fake/bin")

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv

    monkeypatch.setattr(entry.subprocess, "Popen", fake_popen)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 0
    assert captured["argv"] == [
        "/fake/bin",
        "-f",
        "/logs/Player.log",
        "-d",
        "/mtga/data",
    ]


def test_main_normal_launch_never_reads_default_ui(monkeypatch):
    """Config is read once for initialization/corruption detection, and the
    desktop binary is probed unconditionally — default_ui no longer exists."""
    from src.configuration import Configuration

    captured = {}

    def fake_read_configuration(file_location=None):
        # A legacy config whose settings still carry default_ui="tkinter"
        # must not influence routing: the result is discarded entirely.
        captured["read"] = True
        return Configuration(), True

    monkeypatch.setattr(entry.sys, "argv", ["main.py"])
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    monkeypatch.setattr(entry, "read_configuration", fake_read_configuration)
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: "/fake/bin")
    monkeypatch.setattr(
        entry.subprocess, "Popen", lambda argv, **kw: captured.update(argv=argv)
    )
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 0
    assert captured["read"] is True
    assert captured["argv"] == ["/fake/bin"]


def test_main_without_build_exits_two_and_never_falls_through(monkeypatch, capsys):
    """No build anywhere: unified build/dev/MTGA_DRAFT_DESKTOP guidance and
    exit 2 — no fallback UI, no tkinter copy, no --ui flag."""
    from src.configuration import Configuration

    monkeypatch.setattr(entry.sys, "argv", ["main.py"])
    monkeypatch.setattr(entry, "cleanup_old_draft_logs", lambda: None)
    monkeypatch.setattr(entry, "read_configuration", lambda: (Configuration(), False))
    monkeypatch.setattr(entry, "find_desktop_launcher", lambda: None)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "No desktop build found" in out
    assert "npm run tauri dev" in out
    assert "MTGA_DRAFT_DESKTOP" in out
    assert "tkinter" not in out
    assert "--ui" not in out
