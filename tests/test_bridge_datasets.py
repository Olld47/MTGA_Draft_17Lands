"""
tests/test_bridge_datasets.py
Behavioural tests for mtga_bridge.datasets — dataset listing, downloading,
selection and deletion.

This module looked covered: tests/test_bridge_snapshot.py imports from it. But
that import only reaches ChannelStatus / ChannelProgress / ImmediateUI, the
three duck-typed shims that stand in for UI widgets. All four functions
that actually do something were untested, which is how a by-filename search for
coverage misleads.

FileExtractor is patched at its import site (datasets.py binds it with
`from ... import`), following tests/test_download_panel.py:137.
"""

import os
import sys
import time
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
from src.utils import LocalSetInfo

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
    """One row of retrieve_local_set_list's file_list: a LocalSetInfo of
    (set_name, event_type, user_group, start, end, count, path, collected).
    datasets.py reads its named fields set_name/event_type/user_group/file_location."""
    return LocalSetInfo(
        display, event, group, "2024-01-01", "2024-02-01", 1000, path, "2024-02-02"
    )


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


# --- staleness ----------------------------------------------------------------


def test_listing_reports_no_staleness_without_datasets(config):
    with _stub_set_list([]):
        result = datasets.list_local_datasets(config)

    assert result.newest_age_days == -1
    assert result.stale is False
    assert result.last_sync_date == ""


def test_listing_is_fresh_when_the_newest_dataset_is_today(config, sets_folder):
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    now = time.time()
    os.utime(path, (now, now))

    with _stub_set_list([_row(str(path))]):
        result = datasets.list_local_datasets(config)

    assert result.newest_age_days == 0
    assert result.stale is False


def test_listing_flags_stale_when_the_newest_dataset_is_old(config, sets_folder):
    """The core of issue05's staleness acceptance: a local dataset far older
    than today must surface on the Datasets page, not stay silent."""
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")
    # 60s of slack: Windows os.utime rounds the float timestamp up by up to a
    # second, which would land `now - mtime` just under 8 days and flip the
    # whole-day count to 7. 8 days + 60s still counts as 8.
    old = time.time() - (8 * 86400 + 60)
    os.utime(path, (old, old))

    with _stub_set_list([_row(str(path))]):
        result = datasets.list_local_datasets(config)

    assert result.newest_age_days == 8
    assert result.stale is True


def test_listing_ignores_deleted_files_when_measuring_freshness(config, sets_folder):
    """A row whose file vanished reports zeroes and must not drag the newest
    age down to 'just now' — the deleted row's 0.0 mtime is not fresh data."""
    missing = sets_folder / "GONE_PremierDraft_All_Data.json"
    current = sets_folder / "TEST_PremierDraft_All_Data.json"
    current.write_text("{}")
    old = time.time() - (8 * 86400 + 60)
    os.utime(current, (old, old))

    with _stub_set_list([_row(str(missing)), _row(str(current))]):
        result = datasets.list_local_datasets(config)

    assert result.newest_age_days == 8
    assert result.stale is True


def test_listing_surfaces_the_last_successful_sync_date(config, sets_folder):
    config.card_data.last_auto_sync_date = "2026-08-13"
    path = sets_folder / "TEST_PremierDraft_All_Data.json"
    path.write_text("{}")

    with _stub_set_list([_row(str(path))]):
        result = datasets.list_local_datasets(config)

    assert result.last_sync_date == "2026-08-13"


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
        "src.advisor.deck_builder.clear_deck_cache"
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
        "src.advisor.deck_builder.clear_deck_cache"
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


# --- build_set_metrics_vm -----------------------------------------------------


class _FakeMetrics:
    """Duck-types SetMetrics.get_metrics: mean varies by color so the VM rows
    are distinguishable, std is constant."""

    def get_metrics(self, color, field):
        return (55.0 + len(color), 3.0)


class _FakeScanner:
    def __init__(self, metrics):
        self._metrics = metrics

    def retrieve_set_metrics(self):
        return self._metrics


def test_build_set_metrics_vm_covers_every_field_and_color():
    """The frontend formats Grade/Rating from this table, so it must expose
    every WIN_RATE_OPTIONS field across every DECK_COLORS bucket."""
    vm = datasets.build_set_metrics_vm(_FakeScanner(_FakeMetrics()))

    assert vm.has_data is True
    assert set(vm.metrics.keys()) == set(constants.WIN_RATE_OPTIONS)
    for field in constants.WIN_RATE_OPTIONS:
        assert set(vm.metrics[field].keys()) == set(constants.DECK_COLORS)
        for color in constants.DECK_COLORS:
            entry = vm.metrics[field][color]
            assert entry.mean == 55.0 + len(color)
            assert entry.std == 3.0


def test_build_set_metrics_vm_reports_no_data_without_a_dataset():
    vm = datasets.build_set_metrics_vm(_FakeScanner(None))

    assert vm.has_data is False
    assert vm.metrics == {}


def test_build_set_metrics_vm_survives_a_failing_scanner():
    class _Broken:
        def retrieve_set_metrics(self):
            raise RuntimeError("no dataset loaded")

    vm = datasets.build_set_metrics_vm(_Broken())

    assert vm.has_data is False
    assert vm.metrics == {}


# --- build_dataset_switcher_vm -------------------------------------------------


class _SwitcherScanner:
    def __init__(self, set_code, draft_label=""):
        self._set = set_code
        self._label = draft_label

    def retrieve_current_limited_event(self):
        return self._set, self._label


def _switcher_rows(sets_folder):
    """TEST PremierDraft (All + Gold) and TEST QuickDraft (All), plus a foreign
    set that must be filtered out."""
    return [
        _row(str(sets_folder / "TEST_PremierDraft_All_Data.json")),
        _row(
            str(sets_folder / "TEST_PremierDraft_Gold_Data.json"),
            event="PremierDraft",
            group="Gold",
        ),
        _row(str(sets_folder / "TEST_QuickDraft_All_Data.json"), event="QuickDraft"),
        _row(str(sets_folder / "OTHER_PremierDraft_All_Data.json"), display="OTHER"),
    ]


def test_switcher_is_empty_without_a_detected_set(config, sets_folder):
    with _stub_set_list(_switcher_rows(sets_folder)):
        vm = datasets.build_dataset_switcher_vm(_SwitcherScanner(""), config)

    assert vm.set_code == ""
    assert vm.events == []


def test_switcher_groups_local_datasets_by_event_and_group(config, sets_folder):
    with _stub_set_list(_switcher_rows(sets_folder)):
        vm = datasets.build_dataset_switcher_vm(_SwitcherScanner("TEST"), config)

    assert vm.set_code == "TEST"
    assert [e.name for e in vm.events] == ["PremierDraft", "QuickDraft"]
    premier = vm.events[0]
    assert [g.name for g in premier.groups] == ["All", "Gold"]
    assert premier.groups[0].path.endswith("TEST_PremierDraft_All_Data.json")
    assert premier.groups[1].path.endswith("TEST_PremierDraft_Gold_Data.json")
    # The OTHER set's row never leaks in.
    assert all("OTHER" not in g.path for e in vm.events for g in e.groups)


def test_switcher_reports_the_loaded_dataset_as_active(config, sets_folder):
    config.card_data.latest_dataset = "TEST_PremierDraft_Gold_Data.json"
    with _stub_set_list(_switcher_rows(sets_folder)):
        vm = datasets.build_dataset_switcher_vm(_SwitcherScanner("TEST"), config)

    assert vm.active_event == "PremierDraft"
    assert vm.active_group == "Gold"


def test_switcher_normalizes_hyphenated_set_codes(config, sets_folder):
    """17Lands set codes can arrive with a dash; they must still line up with
    the dash-stripped file names (top_bar.update_data_sources behavior)."""
    with _stub_set_list(_switcher_rows(sets_folder)):
        vm = datasets.build_dataset_switcher_vm(_SwitcherScanner("TE-ST"), config)

    assert vm.set_code == "TE-ST"
    assert [e.name for e in vm.events] == ["PremierDraft", "QuickDraft"]
