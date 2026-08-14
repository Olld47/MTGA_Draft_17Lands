import pytest
from unittest.mock import MagicMock, patch
from src.ui.app_controller import AppController
from src.orchestrator import RefreshMessage, StatusMessage


class TestAppController:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.root = MagicMock()
        app._initialized = True
        app._loading = False
        app._rebuilding_ui = False

        # Scanner & Orchestrator mocks
        scanner = MagicMock()
        scanner.lock.acquire.return_value = True
        scanner.retrieve_current_limited_event.return_value = ("OTJ", "PremierDraft")
        scanner.retrieve_current_pack_and_pick.return_value = (1, 1)

        mock_metrics = MagicMock()
        mock_metrics.get_metrics.return_value = (55.0, 4.0)
        scanner.retrieve_set_metrics.return_value = mock_metrics

        scanner.retrieve_tier_data.return_value = {}
        scanner.retrieve_taken_cards.return_value = []
        scanner.retrieve_current_pack_cards.return_value = []
        scanner.retrieve_current_missing_cards.return_value = []
        scanner.retrieve_current_picked_cards.return_value = []
        scanner.retrieve_draft_history.return_value = []

        orchestrator = MagicMock()
        orchestrator.scanner = scanner
        # Emulate empty queue
        orchestrator.update_queue.empty.return_value = True

        app.orchestrator = orchestrator
        return app

    def test_update_loop_processes_queue(self, mock_app):
        """Verify that the update loop drains the orchestrator's typed queue and applies UI updates."""
        controller = AppController(mock_app)

        # Inject typed messages into the mock queue
        import queue

        mock_queue = queue.Queue()
        mock_queue.put(StatusMessage(text="Scanning Log..."))
        mock_queue.put(RefreshMessage())
        mock_app.orchestrator.update_queue = mock_queue

        # Temporarily disable the recursive `after` call to prevent infinite loops
        mock_app.root.after = MagicMock()

        with patch.object(controller, "refresh_ui_data") as mock_refresh:
            controller.update_loop()

            # Verify the status variable was updated
            mock_app.vars["status_text"].set.assert_any_call("Scanning Log...")

            # Verify a full UI refresh was triggered by the RefreshMessage
            mock_refresh.assert_called_once()

            # Verify the loop scheduled itself again
            mock_app.root.after.assert_called_once()

    def test_update_loop_logs_unknown_messages(self, mock_app):
        """An unrecognized queue message must be logged loudly, never silently dropped.

        This is the fail-loud signal that keeps both consumers honest when a new
        message type is added to the queue protocol (architecture-review issue04)."""
        controller = AppController(mock_app)

        import queue

        mock_queue = queue.Queue()
        mock_queue.put("REFRESH")  # legacy bare-string format is gone
        mock_app.orchestrator.update_queue = mock_queue

        mock_app.root.after = MagicMock()

        with patch.object(controller, "refresh_ui_data") as mock_refresh:
            with patch("src.ui.app_controller.logger") as mock_logger:
                controller.update_loop()

        mock_logger.warning.assert_called_once()
        mock_refresh.assert_not_called()

    def test_force_reload_triggers_deep_scan(self, mock_app):
        """Verify the Reload button aggressively wipes state and requests a full scan."""
        controller = AppController(mock_app)
        controller.force_reload()

        mock_app.vars["status_text"].set.assert_called_with("Deep Scanning Log...")
        mock_app.orchestrator.scanner.clear_draft.assert_called_with(True)
        mock_app.orchestrator.trigger_full_scan.assert_called_once()

    def test_check_background_updates(self, mock_app):
        """Background checks only run the dataset sync; the legacy AppUpdate
        polling thread was deleted (architecture-review issue03) — the desktop
        app owns update notifications now, so no app-update thread may spawn."""
        controller = AppController(mock_app)

        controller.check_background_updates()

        mock_app.notifications.check_dataset.assert_called_once()

    def test_on_dataset_update_clears_cache(self, mock_app):
        """Verify loading a new dataset invalidates the mathematical cache."""
        controller = AppController(mock_app)

        mock_app.configuration.card_data.latest_dataset = "M10_Data.json"

        with patch("os.path.exists", return_value=True):
            with patch("src.advisor.deck_builder.clear_deck_cache") as mock_clear:
                with patch.object(controller, "refresh_ui_data") as mock_refresh:
                    controller.on_dataset_update()

                    # Should have reset the cache, requested math update, and triggered UI refresh
                    mock_clear.assert_called_once()
                    mock_app.orchestrator.request_math_update.assert_called_once()
                    mock_refresh.assert_called_once()

    def test_refresh_ui_data_skips_if_locked(self, mock_app):
        """Verify the UI skips rendering if the background thread holds the scanner lock."""
        controller = AppController(mock_app)

        # Simulate background thread currently writing data
        mock_app.orchestrator.scanner.lock.acquire.return_value = False

        # Capture the after() call
        mock_app.root.after = MagicMock()

        controller.refresh_ui_data()

        # It should NOT have accessed any scanner data
        mock_app.orchestrator.scanner.retrieve_current_limited_event.assert_not_called()

        # It SHOULD have rescheduled itself to try again in 100ms
        mock_app.root.after.assert_called_once_with(100, controller.refresh_ui_data)
