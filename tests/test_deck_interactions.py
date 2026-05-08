"""
tests/test_deck_interactions.py
Validates the UX logic for Custom Deck Builder and Sealed Studio.
Specifically ensures single-clicks do NOT move cards (preventing accidental transfers),
while double-clicks and distinct drags DO move cards.
"""

import pytest
import tkinter
from unittest.mock import MagicMock
from src.ui.windows.custom_deck import CustomDeckPanel
from src.configuration import Configuration


class TestDeckInteractions:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_app_context(self):
        draft_manager = MagicMock()
        draft_manager.retrieve_taken_cards.return_value = [
            {"name": "Test Card", "count": 2, "types": ["Creature"]}
        ]
        return draft_manager

    def test_single_click_does_not_move_card(self, root, mock_app_context):
        """Verify that a single click (dx<5, dy<5) does NOT transfer the card."""
        panel = CustomDeckPanel(root, mock_app_context, Configuration(), MagicMock())
        panel.refresh()

        # Seed the panel so the card is in the sideboard list initially
        assert len(panel.sb_list) == 1
        assert len(panel.deck_list) == 0

        # Simulate a press
        panel._drag_data = {
            "name": "Test Card",
            "x": 100,
            "y": 100,
            "is_sb": True,
        }

        # Simulate a release exactly where we pressed (Single Click)
        class MockEvent:
            x_root = 100
            y_root = 100

        panel._on_drag_release(MockEvent(), panel.sb_manager.tree, is_sb=True)

        # Assert: Card MUST still be in the sideboard
        assert len(panel.sb_list) == 1
        assert len(panel.deck_list) == 0

    def test_double_click_moves_card(self, root, mock_app_context):
        """Verify that a true double click instantly transfers the card."""
        panel = CustomDeckPanel(root, mock_app_context, Configuration(), MagicMock())
        panel.refresh()

        # Setup
        assert len(panel.sb_list) == 1
        assert len(panel.deck_list) == 0

        # Mock the tree identifying the row successfully
        tree_mock = MagicMock()
        tree_mock.identify_row.return_value = "row_1"

        # Override _get_card_from_row to return our test card directly
        panel._get_card_from_row = lambda tree, row, is_sb: {"name": "Test Card"}

        # Fire Double Click
        panel._on_double_click(MagicMock(), tree_mock, is_sb=True)

        # Assert: Card MUST have transferred to the Main Deck
        assert len(panel.sb_list) == 0
        assert len(panel.deck_list) == 1
        assert panel.deck_list[0]["name"] == "Test Card"

    def test_drag_and_drop_moves_card(self, root, mock_app_context):
        """Verify that a click followed by movement (dx>=5) transfers the card."""
        panel = CustomDeckPanel(root, mock_app_context, Configuration(), MagicMock())
        panel.refresh()

        # Setup
        assert len(panel.sb_list) == 1
        assert len(panel.deck_list) == 0

        # Simulate press
        panel._drag_data = {
            "name": "Test Card",
            "x": 100,
            "y": 100,
            "is_sb": True,
        }

        # Simulate a release far away inside the target widget bounding box
        class MockEvent:
            x_root = 150
            y_root = 150

        # Mock the boundary checker to pretend we dropped it in the Main Deck frame
        panel._inside_widget = lambda e, widget: widget == panel.deck_frame

        panel._on_drag_release(MockEvent(), panel.sb_manager.tree, is_sb=True)

        # Assert: Card MUST have transferred to the Main Deck
        assert len(panel.sb_list) == 0
        assert len(panel.deck_list) == 1
