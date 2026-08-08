import pytest
import json
import gzip
import os
from unittest.mock import patch, MagicMock
from src.dataset_updater import DatasetUpdater


@pytest.fixture
def updater(tmp_path, monkeypatch):
    # Route the application's SETS_FOLDER to a temporary test directory
    monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
    return DatasetUpdater(config=MagicMock())


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_downloads_new_files(mock_get, updater, tmp_path):
    # 1. Mock the remote manifest response
    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "active_sets": ["MH3"],
        "datasets": {
            "MH3_PremierDraft_All": {
                "hash": "fake_hash_123",
                "filename": "MH3_PremierDraft_All_Data.json.gz",
            }
        },
    }

    # 2. Mock the GZIP file download response
    mock_gz_response = MagicMock()
    mock_gz_response.status_code = 200
    mock_gz_response.content = gzip.compress(b'{"mock_card": "data"}')

    # 3. Mock the 17Lands live-formats endpoint (MH3 Premier Draft is live)
    mock_filters_response = MagicMock()
    mock_filters_response.status_code = 200
    mock_filters_response.json.return_value = {
        "live_formats_by_expansion": {"MH3": ["PremierDraft"]}
    }

    # Wire the mock to return manifest first, then gz data
    mock_get.side_effect = [
        MagicMock(
            status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}
        ),  # Health check
        mock_manifest_response,  # Manifest
        mock_filters_response,  # 17Lands live formats
        mock_gz_response,  # Dataset download
    ]

    progress_mock = MagicMock()

    # Act
    updater.sync_datasets(progress_mock)

    # Assert
    # Verify the GZ file was extracted and saved correctly as a standard JSON
    target_file = tmp_path / "MH3_PremierDraft_All_Data.json"
    assert target_file.exists()

    with open(target_file, "r") as f:
        data = json.load(f)
        assert data["mock_card"] == "data"

    # Verify local manifest was updated
    local_manifest = updater.get_local_manifest()
    assert "MH3_PremierDraft_All" in local_manifest["datasets"]
    assert local_manifest["datasets"]["MH3_PremierDraft_All"]["hash"] == "fake_hash_123"


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_skips_existing_hashes(mock_get, updater, tmp_path):
    # Arrange: Create a local manifest that already matches the remote hash
    updater.save_local_manifest(
        {"datasets": {"MH3_PremierDraft_All": {"hash": "matched_hash"}}}
    )

    # We must also create the local file so file_missing is False
    (tmp_path / "MH3_PremierDraft_All_Data.json").write_text("dummy")

    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "datasets": {
            "MH3_PremierDraft_All": {
                "hash": "matched_hash",
                "filename": "MH3_PremierDraft_All_Data.json.gz",
            }
        }
    }

    mock_filters_response = MagicMock()
    mock_filters_response.status_code = 200
    mock_filters_response.json.return_value = {
        "live_formats_by_expansion": {"MH3": ["PremierDraft"]}
    }

    # Mock sequence: Health -> Filters -> Manifest -> (NO GZIP DOWNLOAD EXPECTED)
    mock_get.side_effect = [
        MagicMock(
            status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}
        ),
        mock_manifest_response,
        mock_filters_response,
    ]

    progress_mock = MagicMock()

    # Act
    updater.sync_datasets(progress_mock)

    # Assert: Network was only hit three times (Health + Filters + Manifest),
    # meaning the file download was skipped
    assert mock_get.call_count == 3


def test_dataset_key_splitting():
    from src.dataset_updater import _dataset_set_format

    assert _dataset_set_format("MSH_PremierDraft_All") == ("MSH", "PremierDraft")
    assert _dataset_set_format("Cube - Powered_TradDraft_Top") == (
        "Cube - Powered",
        "TradDraft",
    )
    assert _dataset_set_format("malformed") == (None, None)


def test_is_live_dataset_matches_only_exact_expansion_and_format():
    from src.dataset_updater import _is_live_dataset

    live = {"MSH": ["PremierDraft", "TradDraft"], "WAR": ["PremierDraft"]}

    assert _is_live_dataset("MSH_PremierDraft_All", live)
    assert _is_live_dataset("MSH_TradDraft_Top", live)
    assert _is_live_dataset("WAR_PremierDraft_All", live)
    # Same set, non-live format → excluded (no auto-download of Sealed)
    assert not _is_live_dataset("MSH_Sealed_All", live)
    # Non-live set → excluded
    assert not _is_live_dataset("TMT_PremierDraft_All", live)
    # A rotated cube must never be served for a live one of a different name
    assert not _is_live_dataset("Cube - Powered_PremierDraft_All", live)
    # Malformed keys can't match anything
    assert not _is_live_dataset("not_a_dataset_key", live)


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_downloads_only_live_draft_formats(mock_get, updater, tmp_path):
    """A fresh install downloads the currently-live draft sets only — the
    manifest's other 80+ datasets (rotated sets, and a live set's Sealed)
    stay on the server."""
    manifest_datasets = {
        "MSH_PremierDraft_All": {
            "hash": "h_msh_p", "filename": "MSH_PremierDraft_All_Data.json.gz"
        },
        "MSH_Sealed_All": {
            "hash": "h_msh_s", "filename": "MSH_Sealed_All_Data.json.gz"
        },
        "TMT_PremierDraft_All": {
            "hash": "h_tmt_p", "filename": "TMT_PremierDraft_All_Data.json.gz"
        },
    }
    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "active_sets": ["MSH", "TMT"],
        "datasets": manifest_datasets,
    }
    mock_filters_response = MagicMock()
    mock_filters_response.status_code = 200
    mock_filters_response.json.return_value = {
        "live_formats_by_expansion": {"MSH": ["PremierDraft"]}
    }

    def gz_response():
        r = MagicMock()
        r.status_code = 200
        r.content = gzip.compress(b'{"card": "data"}')
        return r

    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}),
        mock_manifest_response,
        mock_filters_response,
        # Enough gz responses for every manifest dataset, so that a wrongly
        # scoped download SUCCEEDS and is caught by the file assertions below
        # instead of silently dying on an exhausted mock.
        gz_response(),
        gz_response(),
        gz_response(),
    ]

    updater.sync_datasets(MagicMock())

    assert (tmp_path / "MSH_PremierDraft_All_Data.json").exists()
    assert not (tmp_path / "MSH_Sealed_All_Data.json").exists()
    assert not (tmp_path / "TMT_PremierDraft_All_Data.json").exists()
    local = updater.get_local_manifest()
    assert set(local["datasets"]) == {"MSH_PremierDraft_All"}
    # Health + Manifest + Filters + exactly one download.
    assert mock_get.call_count == 4


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_falls_back_to_active_sets_when_filters_fail(mock_get, updater, tmp_path):
    """If the 17Lands filters endpoint is unreachable, scope to the manifest's
    own active_sets so a fresh install still gets the current set."""
    manifest_datasets = {
        "MSH_PremierDraft_All": {
            "hash": "h_msh", "filename": "MSH_PremierDraft_All_Data.json.gz"
        },
        "TMT_PremierDraft_All": {
            "hash": "h_tmt", "filename": "TMT_PremierDraft_All_Data.json.gz"
        },
    }
    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "active_sets": ["MSH"],
        "datasets": manifest_datasets,
    }
    failing_filters = MagicMock()
    failing_filters.raise_for_status.side_effect = Exception("network down")

    def gz_response():
        r = MagicMock()
        r.status_code = 200
        r.content = gzip.compress(b'{"card": "data"}')
        return r

    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}),
        mock_manifest_response,
        failing_filters,
        # Two gz responses so a wrongly-scoped TMT download would SUCCEED and
        # be caught by the file/call-count assertions instead of dying on an
        # exhausted mock.
        gz_response(),
        gz_response(),
    ]

    updater.sync_datasets(MagicMock())

    assert (tmp_path / "MSH_PremierDraft_All_Data.json").exists()
    assert not (tmp_path / "TMT_PremierDraft_All_Data.json").exists()
    # Health + Manifest + Filters + exactly one download (MSH only).
    assert mock_get.call_count == 4


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_downloads_everything_when_no_live_info(mock_get, updater, tmp_path):
    """Last-resort degradation: with neither filters nor active_sets, download
    the whole manifest rather than leave a fresh install empty."""
    manifest_datasets = {
        "MSH_PremierDraft_All": {
            "hash": "h_msh", "filename": "MSH_PremierDraft_All_Data.json.gz"
        },
        "TMT_PremierDraft_All": {
            "hash": "h_tmt", "filename": "TMT_PremierDraft_All_Data.json.gz"
        },
    }
    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {"datasets": manifest_datasets}
    failing_filters = MagicMock()
    failing_filters.raise_for_status.side_effect = Exception("network down")

    def gz_response():
        r = MagicMock()
        r.status_code = 200
        r.content = gzip.compress(b'{"card": "data"}')
        return r

    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}),
        mock_manifest_response,
        failing_filters,
        gz_response(),
        gz_response(),
    ]

    updater.sync_datasets(MagicMock())

    assert (tmp_path / "MSH_PremierDraft_All_Data.json").exists()
    assert (tmp_path / "TMT_PremierDraft_All_Data.json").exists()
