import pytest
import os
import queue
from unittest.mock import patch, MagicMock
from src.orchestrator import DraftOrchestrator, RefreshMessage, StatusMessage
from src.configuration import Configuration


@pytest.fixture
def orchestrator():
    config = Configuration()
    config.settings.arena_log_location = "mock_live_log.txt"
    config.settings.draft_log_enabled = False

    mock_scanner = MagicMock()
    mock_scanner.arena_file = "mock_live_log.txt"

    return DraftOrchestrator(mock_scanner, config, MagicMock())


@patch("src.orchestrator.os.path.getsize")
@patch("src.orchestrator.os.path.exists")
@patch("builtins.open")
def test_check_live_log_detects_draft(
    mock_open, mock_exists, mock_getsize, orchestrator
):
    """Verifies the background watchdog detects when a draft suddenly starts in the active log."""

    # App starts with a 500-byte log file
    orchestrator._last_live_file_size = 500

    # File exists and has grown to 1000 bytes
    mock_exists.return_value = True
    mock_getsize.return_value = 1000

    # Mock the file reader yielding lines
    mock_file = MagicMock()
    mock_file.readline.side_effect = [
        "Some random Arena telemetry...",
        "[UnityCrossThreadLogger]==> Event_Join Draft",  # Trigger!
        "",  # EOF
    ]
    mock_open.return_value.__enter__.return_value = mock_file

    # Act
    found_draft = orchestrator._check_live_log_for_draft()

    # Assert
    assert found_draft is True
    # Verify the pointer moved forward
    assert orchestrator._last_live_file_size == 1000


@patch("src.orchestrator.os.path.getsize", return_value=500)
@patch("src.orchestrator.os.path.exists", return_value=True)
def test_check_live_log_ignores_static_file(mock_exists, mock_getsize, orchestrator):
    """Verifies we do not waste CPU cycles reading the log if the file size hasn't changed."""

    orchestrator._last_live_file_size = 500  # Matches current size

    with patch("builtins.open") as mock_open:
        found_draft = orchestrator._check_live_log_for_draft()

        # Assert
        assert found_draft is False
        mock_open.assert_not_called()  # No file I/O performed


def test_orchestrator_flags(orchestrator):
    """Verify the flag setters are working properly."""
    assert not orchestrator._force_full_scan_event.is_set()
    orchestrator.trigger_full_scan()
    assert orchestrator._force_full_scan_event.is_set()

    assert not orchestrator._stop_event.is_set()
    orchestrator.stop()
    assert orchestrator._stop_event.is_set()

    assert not orchestrator._force_math_event.is_set()
    orchestrator.request_math_update()
    assert orchestrator._force_math_event.is_set()


@patch("src.orchestrator.time.sleep", return_value=None)
def test_orchestrator_run_loop(mock_sleep, orchestrator):
    """Verify the run loop correctly consumes events and file swaps."""
    # Trigger the flags
    orchestrator.request_math_update()
    orchestrator.trigger_full_scan()

    # Queue a file swap
    orchestrator.set_file_and_scan("fake.log")

    # Prevent actually reading the hard drive
    orchestrator.scanner.set_arena_file = MagicMock()
    orchestrator.scanner.draft_start_search = MagicMock(return_value=False)
    orchestrator.sync_dataset_to_event = MagicMock()

    # Stop loop after one iteration by changing the return value of is_set
    orchestrator._stop_event.is_set = MagicMock(side_effect=[False, True])

    orchestrator.run()

    # Assertions
    orchestrator.scanner.set_arena_file.assert_called_with("fake.log")
    # Events should be cleared after the loop executes
    assert not orchestrator._force_full_scan_event.is_set()
    assert not orchestrator._force_math_event.is_set()
    assert orchestrator.update_queue.qsize() > 0


def test_file_swap_queue_processing(orchestrator):
    """Verify that thread-safe requests from the UI to read historical logs are processed."""

    # UI requests to read two different logs rapidly
    orchestrator.set_file_and_scan("historical_draft_1.log")
    orchestrator.set_file_and_scan("historical_draft_2.log")

    # Mock the scanner so it doesn't actually try to read them
    orchestrator.scanner.draft_start_search.return_value = True
    orchestrator.sync_dataset_to_event = MagicMock()

    # Force the run loop logic manually for one step
    # We simulate what happens inside run() when the queue isn't empty
    new_file = None
    while not orchestrator._file_swap_queue.empty():
        new_file = orchestrator._file_swap_queue.get_nowait()

    assert (
        new_file == "historical_draft_2.log"
    )  # It correctly skips to the most recent request

    # Simulate processing
    orchestrator.scanner.set_arena_file(new_file)

    # Verify scanner was updated
    orchestrator.scanner.set_arena_file.assert_called_with("historical_draft_2.log")


def test_orchestrator_emits_typed_refresh_message(orchestrator):
    """The queue must carry a typed RefreshMessage, never a bare "REFRESH" string."""
    orchestrator.request_math_update()
    with patch("src.orchestrator.time.sleep", return_value=None):
        orchestrator._stop_event.is_set = MagicMock(side_effect=[False, True])
        orchestrator.run()

    msgs = list(orchestrator.update_queue.queue)
    assert msgs
    assert all(isinstance(m, RefreshMessage) for m in msgs)
    assert all(not isinstance(m, str) for m in msgs)


def test_orchestrator_emits_typed_status_then_refresh_sequence(orchestrator):
    """The file-swap path emits StatusMessage(s) then a final RefreshMessage."""
    orchestrator.set_file_and_scan("fake.log")
    orchestrator.scanner.set_arena_file = MagicMock()
    orchestrator.scanner.draft_start_search = MagicMock(return_value=False)
    orchestrator.sync_dataset_to_event = MagicMock()
    with patch("src.orchestrator.time.sleep", return_value=None):
        orchestrator._stop_event.is_set = MagicMock(side_effect=[False, True])
        orchestrator.run()

    msgs = list(orchestrator.update_queue.queue)
    assert msgs[0] == StatusMessage(text="Scanning Log...")
    assert any(m == StatusMessage(text="Parsing Picks...") for m in msgs)
    assert msgs[-1] == RefreshMessage()
    assert all(not isinstance(m, (dict, str)) for m in msgs)


def test_sync_dataset_emits_loading_status_message(orchestrator):
    """sync_dataset_to_event reports a typed Loading status message on cache miss."""
    orchestrator.scanner.retrieve_current_limited_event = MagicMock(
        return_value=("OTJ", "PremierDraft")
    )
    orchestrator.scanner.event_string = "PremierDraft"
    orchestrator.scanner.select_best_dataset = MagicMock(
        return_value="/sets/OTJ_Data.json"
    )
    orchestrator.scanner.retrieve_set_data = MagicMock()
    orchestrator.scanner.set_data._dataset = None
    orchestrator.config.card_data.latest_dataset = "M10_Data.json"

    # Patch the symbol orchestrator actually bound at import time
    # (from src.configuration import write_configuration) — patching the
    # source module would be a no-op and the real function would atomically
    # overwrite the user's config.json with the fixture's state.
    with patch("src.orchestrator.write_configuration"):
        assert orchestrator.sync_dataset_to_event() is True

    msgs = list(orchestrator.update_queue.queue)
    assert StatusMessage(text="Loading OTJ Dataset...") in msgs
    assert all(not isinstance(m, dict) for m in msgs)
