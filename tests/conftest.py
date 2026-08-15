"""
tests/conftest.py
Global pytest configuration and fixtures.
"""

import pytest


@pytest.fixture(autouse=True)
def patch_dataset_skip_unresolved():
    """Ensure the Dataset class does not drop unresolved IDs during tests so we can verify pipeline tracking."""
    from src.dataset import Dataset

    original = Dataset.skip_unresolved_ids
    Dataset.skip_unresolved_ids = False
    yield
    Dataset.skip_unresolved_ids = original
