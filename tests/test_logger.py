import os
import subprocess
import sys
import uuid

import pytest
import logging
from src.logger import create_logger, CustomFormatter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_create_logger():
    logger = create_logger()
    assert logger.name == "debug_log"
    assert logger.level == logging.DEBUG


def test_custom_formatter():
    formatter = CustomFormatter()
    record = logging.LogRecord("name", logging.ERROR, "pathname", 1, "msg", None, None)
    formatted = formatter.format(record)
    assert "msg" in formatted
    assert "ERROR" in formatted

    record_info = logging.LogRecord(
        "name", logging.INFO, "pathname", 1, "info msg", None, None
    )
    formatted_info = formatter.format(record_info)
    assert "info msg" in formatted_info
    assert "INFO" in formatted_info


# --- import-time purity guard (hermeticity) ----------------------------------


def test_importing_logger_writes_nothing_to_disk(tmp_path):
    """Guard: importing src.logger must not create Debug/ or debug.log
    anywhere. Runs in a subprocess with the writable base redirected to a
    temp root because the module is already imported in this process."""
    base = tmp_path / "base"
    base.mkdir()
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    env["MTGA_DRAFT_BASE_DIR"] = str(base)
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [sys.executable, "-c", "import src.logger"],
        cwd=str(base),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    leftovers = [
        str(p)
        for p in base.rglob("*")
        if p.name in {"Debug", "debug.log", "MTGA_Draft_Tool"}
    ]
    assert leftovers == [], f"import created files under base: {leftovers}"


def test_logger_creates_debug_file_on_first_record(tmp_path):
    """The deferred file handler materializes Debug/debug.log on the first
    emitted record — exactly once, never duplicated per record."""
    base = tmp_path / "base"
    base.mkdir()
    token = f"HERMETIC_PROBE_{uuid.uuid4().hex}"
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    env["MTGA_DRAFT_BASE_DIR"] = str(base)

    code = (
        "import src.logger\n"
        "from src.logger import create_logger\n"
        f"create_logger().info('{token}')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(base),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    log_file = base / "Debug" / "debug.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert content.count(token) == 1
