"""
tests/test_bridge_datasets.py
Behavioural tests for mtga_bridge.datasets — dataset listing, downloading,
selection and deletion.

This module looked covered: tests/test_bridge_snapshot.py imports from it. But
that import only reaches ChannelStatus / ChannelProgress / ImmediateUI, the
three duck-typed shims that stand in for tkinter widgets. All four functions
that actually do something were untested, which is how a by-filename search for
coverage misleads.

FileExtractor is patched at its import site (datasets.py binds it with
`from ... import`), following tests/test_download_panel.py:137.
"""

import os
import sys
from unittest.mock import MagicMock, patch

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

from src import constants
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo

from mtga_bridge import datasets


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def config():
    cfg = Configuration()
    cfg.card_data.latest_dataset = ""
    return cfg


@pytest.fixture
def sets_folder(tmp_path, monkeypatch):
    """delete_dataset reads constants.SETS_FOLDER as an attribute, so patching
    src.constants reaches it. Note src/utils.py imports SETS_FOLDER by name and
    does *not* follow this patch — hence retrieve_local_set_list is stubbed
    rather than driven through a real folder."""
    folder = tmp_path / "Sets"
    folder.mkdir()
    monkeypatch.setattr("src.constants.SETS_FOLDER", str(folder))
    return folder


def _row(path, display="TEST", event="PremierDraft", group="All"):
    """One row of retrieve_local_set_list's file_list: an 8-tuple of
    (display, event, group, start, end, count, path, collected). datasets.py
    reads indices 0, 1, 2 and 6."""
    return (display, event, group, "2024-01-01", "2024-02-01", 1000, path, "2024-02-02")


def _stub_set_list(rows):
    return patch("mtga_bridge.datasets.retrieve_local_set_list", return_value=(rows, []))


def _sets_data(start_date=constants.START_DATE_DEFAULT, codes=("TEST",)):
    return SetDictionary(
        data={
            "Test Set": SetInfo(
                arena=list(codes),
                seventeenlands=list(codes),
                set_code=codes[0],
                start_date=start_date,
            )
        }
    ).data


# --- list_local_datasets -----------------------------------------------------


def test_listing_is_empty_when_no_files_exist(config):
    with _stub_set_list([]):
        result = datasets.list_local_datasets(config)

    assert result.datasets == []
    assert result.active_dataset is None


def test_listing_describes_each_dataset(config, sets_folder):
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text('{"meta": {}}')

    with _stub_set_list([_row(str(path))]):
        result = datasets.list_local_datasets(config)

    info = result.datasets[0]
    assert info.label == "[TEST] PremierDraft (All)"
    assert info.path == str(path)
    assert info.file_name == "TEST_PremierDraft_All_Data.json"
    assert info.size_bytes == len('{"meta": {}}')
    assert info.modified > 0


def test_listing_flags_the_active_dataset(config, sets_folder):
    active = sets_folder / "TEST_PremierDraft_All_Data.json"
    other = sets_folder / "OTHER_QuickDraft_All_Data.json"
    for path in (active, other):
        path.write_text("{}")
    config.card_data.latest_dataset = active.name

    with _stub_set_list([_row(str(active)), _row(str(other), display="OTHER")]):
        result = datasets.list_local_datasets(config)

    assert result.active_dataset == active.name
    assert [d.is_active for d in result.datasets] == [True, False]


def test_listing_survives_a_file_deleted_under_it(config, sets_folder):
    """The set-list cache can outlive the file it names, so os.stat raises.
    Reporting zeroes beats failing the whole Datasets page."""
    missing = sets_folder / "GONE_PremierDraft_All_Data.json"

    with _stub_set_list([_row(str(missing))]):
        result = datasets.list_local_datasets(config)

    assert result.datasets[0].size_bytes == 0
    assert result.datasets[0].modified == 0.0


def test_listing_treats_a_blank_active_dataset_as_none(config, sets_folder):
    """latest_dataset defaults to "" rather than None; without the `or None`
    an unset value would compare equal to nothing and read as a real
    selection."""
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    config.card_data.latest_dataset = ""

    with _stub_set_list([_row(str(path))]):
        result = datasets.list_local_datasets(config)

    assert result.active_dataset is None
    assert result.datasets[0].is_active is False


# --- _resolve_start_date -----------------------------------------------------


def test_start_date_prefers_the_sets_own_value():
    sets_data = _sets_data(start_date="2025-06-10")
    assert datasets._resolve_start_date(sets_data, "Test Set") == "2025-06-10"


def test_start_date_falls_back_to_the_earliest_manifest_entry():
    """A set that carries only the sentinel date is dated from whatever the
    local manifest already downloaded for the same 17Lands code — the earliest
    of them, so no games are missed."""
    manifest = {
        "datasets": {
            "TEST_PremierDraft": {"start_date": "2025-03-01"},
            "TEST_QuickDraft": {"start_date": "2025-02-01"},
            "OTHER_PremierDraft": {"start_date": "2020-01-01"},
        }
    }
    with patch("mtga_bridge.datasets.read_local_manifest", return_value=manifest):
        resolved = datasets._resolve_start_date(_sets_data(), "Test Set")

    assert resolved == "2025-02-01"


def test_start_date_matches_manifest_codes_case_insensitively():
    manifest = {"datasets": {"test_PremierDraft": {"start_date": "2025-04-01"}}}
    with patch("mtga_bridge.datasets.read_local_manifest", return_value=manifest):
        resolved = datasets._resolve_start_date(_sets_data(), "Test Set")

    assert resolved == "2025-04-01"


def test_start_date_falls_through_to_the_default():
    with patch("mtga_bridge.datasets.read_local_manifest", return_value={}):
        resolved = datasets._resolve_start_date(_sets_data(), "Test Set")

    assert resolved == constants.START_DATE_DEFAULT


def test_start_date_handles_an_unknown_set():
    with patch("mtga_bridge.datasets.read_local_manifest", return_value={}):
        resolved = datasets._resolve_start_date(_sets_data(), "No Such Set")

    assert resolved == constants.START_DATE_DEFAULT


# --- download_dataset_blocking -----------------------------------------------


@pytest.fixture
def extractor():
    """Patches FileExtractor at datasets.py's import binding and shapes the
    two network calls' returns: retrieve_17lands_color_ratings gives a 2-tuple,
    download_card_data a 3-tuple."""
    with patch("mtga_bridge.datasets.FileExtractor") as cls, patch(
        "mtga_bridge.datasets.write_configuration"
    ) as write_config, patch(
        "mtga_bridge.datasets.read_local_manifest", return_value={}
    ):
        instance = cls.return_value
        instance.retrieve_17lands_color_ratings.return_value = (True, 5000)
        instance.download_card_data.return_value = (True, "Success", 1234)
        instance.export_card_data.return_value = "TEST_PremierDraft_All_Data.json"
        instance.write_configuration = write_config
        yield instance


def _download(config, **kwargs):
    params = dict(
        config=config,
        sets_data=_sets_data(),
        set_key="Test Set",
        event_type="PremierDraft",
        user_group="All",
        send=MagicMock(),
    )
    params.update(kwargs)
    return datasets.download_dataset_blocking(**params)


def test_download_rejects_an_unknown_set(config, extractor):
    result = _download(config, set_key="No Such Set")

    assert result.ok is False
    assert "No Such Set" in result.message
    extractor.download_card_data.assert_not_called()


def test_download_reports_a_failed_17lands_connection(config, extractor):
    extractor.retrieve_17lands_color_ratings.return_value = (False, 0)

    result = _download(config)

    assert result.ok is False
    assert result.message == "17Lands Connection Failed"
    extractor.download_card_data.assert_not_called()


def test_download_passes_through_a_card_data_failure(config, extractor):
    extractor.download_card_data.return_value = (False, "Rate limited by 17Lands", 0)

    result = _download(config)

    assert result.ok is False
    assert result.message == "Rate limited by 17Lands"


def test_a_successful_download_becomes_the_active_dataset(config, extractor):
    result = _download(config)

    assert result.ok is True
    assert result.message == "Success"
    assert config.card_data.latest_dataset == "TEST_PremierDraft_All_Data.json"


def test_a_successful_download_persists_the_config(config, extractor):
    with patch("mtga_bridge.datasets.write_configuration") as write_config:
        _download(config)

    write_config.assert_called_once_with(config)


def test_download_configures_the_extractor(config, extractor):
    _download(config, event_type="QuickDraft", user_group="Top")

    extractor.clear_data.assert_called_once_with()
    extractor.set_draft_type.assert_called_once_with("QuickDraft")
    extractor.set_user_group.assert_called_once_with("Top")
    extractor.set_time_period.assert_called_once_with(constants.TIME_PERIOD_DEFAULT)


def test_download_defaults_a_blank_user_group_to_all(config, extractor):
    _download(config, user_group="")
    extractor.set_user_group.assert_called_once_with("All")


def test_download_catches_an_unexpected_failure(config, extractor):
    extractor.download_card_data.side_effect = RuntimeError("disk full")

    result = _download(config)

    assert result.ok is False
    assert "disk full" in result.message


def test_download_refuses_to_run_twice_at_once(config, extractor):
    """_download_lock is a module global. A second call while one is running
    must be turned away rather than queued — two extractors writing the same
    Sets file would interleave."""
    datasets._download_lock.acquire()
    try:
        result = _download(config)
    finally:
        datasets._download_lock.release()

    assert result.ok is False
    assert result.message == "A download is already in progress"


def test_the_lock_is_released_after_a_failure(config, extractor):
    """Without the finally, one failed download would wedge every later one
    behind 'already in progress' for the rest of the session."""
    extractor.download_card_data.side_effect = RuntimeError("boom")
    _download(config)

    assert datasets._download_lock.acquire(blocking=False)
    datasets._download_lock.release()


# --- select_dataset_blocking -------------------------------------------------


def test_selecting_a_missing_file_fails(config, sets_folder):
    result = datasets.select_dataset_blocking(
        MagicMock(), config, str(sets_folder / "nope.json")
    )
    assert result is False


def test_selecting_loads_the_dataset_and_clears_caches(config, sets_folder):
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    scanner = MagicMock()

    with patch("mtga_bridge.datasets.write_configuration"), patch(
        "src.card_logic.clear_deck_cache"
    ) as clear_cache:
        result = datasets.select_dataset_blocking(scanner, config, str(path))

    assert result is True
    scanner.retrieve_set_data.assert_called_once_with(str(path))
    clear_cache.assert_called_once_with()
    assert config.card_data.latest_dataset == path.name


def test_selecting_takes_the_scanner_lock(config, sets_folder):
    """The orchestrator thread is reading the scanner concurrently; swapping
    set data out from under it without the lock is a torn read."""
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    scanner = MagicMock()

    with patch("mtga_bridge.datasets.write_configuration"), patch(
        "src.card_logic.clear_deck_cache"
    ):
        datasets.select_dataset_blocking(scanner, config, str(path))

    scanner.lock.__enter__.assert_called_once_with()


# --- delete_dataset ----------------------------------------------------------


def test_deleting_refuses_a_path_outside_the_sets_folder(config, sets_folder, tmp_path):
    """The path arrives from the frontend, so this guard is the boundary
    between a Datasets-page click and an arbitrary unlink."""
    outsider = tmp_path / "important.json"
    outsider.write_text("{}")

    assert datasets.delete_dataset(config, str(outsider)) is False
    assert outsider.exists()


def test_deleting_refuses_a_traversal_out_of_the_sets_folder(
    config, sets_folder, tmp_path
):
    outsider = tmp_path / "important.json"
    outsider.write_text("{}")
    traversal = os.path.join(str(sets_folder), "..", "important.json")

    assert datasets.delete_dataset(config, traversal) is False
    assert outsider.exists()


def test_deleting_refuses_a_sibling_folder_with_the_same_prefix(config, sets_folder):
    """The guard compares against SETS_FOLDER + os.sep, so a sibling named
    Sets_backup must not pass a plain startswith."""
    sibling = sets_folder.parent / "Sets_backup"
    sibling.mkdir()
    victim = sibling / "TEST_PremierDraft_All_Data.json"
    victim.write_text("{}")

    assert datasets.delete_dataset(config, str(victim)) is False
    assert victim.exists()


def test_deleting_a_missing_file_fails(config, sets_folder):
    assert datasets.delete_dataset(config, str(sets_folder / "nope.json")) is False


def test_deleting_removes_the_file(config, sets_folder):
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")

    with patch("src.utils.drop_local_set_from_cache"):
        assert datasets.delete_dataset(config, str(path)) is True

    assert not path.exists()


def test_deleting_the_active_dataset_clears_the_selection(config, sets_folder):
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    config.card_data.latest_dataset = path.name

    with patch("mtga_bridge.datasets.write_configuration") as write_config, patch(
        "src.utils.drop_local_set_from_cache"
    ):
        datasets.delete_dataset(config, str(path))

    assert config.card_data.latest_dataset == ""
    write_config.assert_called_once_with(config)


def test_deleting_an_inactive_dataset_leaves_the_selection(config, sets_folder):
    active = sets_folder / "TEST_PremierDraft_All_Data.json"
    doomed = sets_folder / "OTHER_QuickDraft_All_Data.json"
    for path in (active, doomed):
        path.write_text("{}")
    config.card_data.latest_dataset = active.name

    with patch("mtga_bridge.datasets.write_configuration") as write_config, patch(
        "src.utils.drop_local_set_from_cache"
    ):
        datasets.delete_dataset(config, str(doomed))

    assert config.card_data.latest_dataset == active.name
    write_config.assert_not_called()


def test_deleting_drops_the_file_from_the_set_list_cache(config, sets_folder):
    """delete_dataset updates the cached set list in place so the next listing
    reflects the removal without a full-folder rescan."""
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")

    with patch("src.utils.drop_local_set_from_cache") as drop:
        datasets.delete_dataset(config, str(path))

    drop.assert_called_once_with(os.path.abspath(str(path)))
