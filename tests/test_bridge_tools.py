"""
tests/test_bridge_tools.py
Bridge-layer tests for the File-menu tool port (mtga_bridge.tools): draft
CSV/JSON export, saving the exported text, and locating the MTGA_Data folder.
Exercised against a real ArenaScanner with a mock card database. No pytauri or
tkinter.
"""

import csv
import io
import json
import os
import sys
from unittest.mock import patch

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

from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.log_scanner import ArenaScanner
from src.utils import Result

from mtga_bridge import tools
from mtga_bridge.runtime import AppRuntime


# --- Fixtures ----------------------------------------------------------------


_POOL_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"], 58.0),
    ("Blue Flyer", 3, ["Creature"], ["U"], 56.0),
    ("Black Removal", 2, ["Instant"], ["B"], 60.0),
    ("Red Burn", 1, ["Instant"], ["R"], 55.0),
]

# GrpIds run 200, 201, ... in _POOL_CARDS order
_CARD_ID = {name: str(200 + i) for i, (name, *_rest) in enumerate(_POOL_CARDS)}


def _mock_dataset():
    return {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            _CARD_ID[name]: {
                "name": name,
                "cmc": cmc,
                "types": types,
                "colors": colors,
                "rarity": "common",
                "mana_cost": "",
                "deck_colors": {
                    "All Decks": {
                        "gihwr": gihwr,
                        "alsa": 3.0,
                        "ata": 4.0,
                        "iwd": 1.5,
                    }
                },
            }
            for name, cmc, types, colors, gihwr in _POOL_CARDS
        },
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    sets_dir = tmp_path / "Sets"
    sets_dir.mkdir()
    temp_dir = tmp_path / "Temp"
    temp_dir.mkdir()

    monkeypatch.setattr("src.constants.SETS_FOLDER", str(sets_dir))
    monkeypatch.setattr("src.constants.TEMP_FOLDER", str(temp_dir))

    log_file = tmp_path / "Player.log"
    log_file.write_text("MTGA Log Start\n")

    dataset_path = sets_dir / "TEST_PremierDraft_All_Data.json"
    data = _mock_dataset()
    dataset_path.write_text(json.dumps(data))

    mock_sets = SetDictionary(
        data={
            "Test Set": SetInfo(arena=["TEST"], seventeenlands=["TEST"], set_code="TEST")
        }
    )

    config = Configuration()
    config.settings.arena_log_location = str(log_file)

    with patch(
        "src.dataset.check_file_integrity", return_value=(Result.VALID, data)
    ):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))

    scanner.draft_sets = ["TEST"]
    runtime = AppRuntime(config=config, scanner=scanner)
    return {
        "runtime": runtime,
        "scanner": scanner,
        "config": config,
        "tmp_path": tmp_path,
    }


def _seed_history(scanner):
    """Two packs; the user took White Knight then Black Removal."""
    scanner.draft_history = [
        {
            "Pack": 1,
            "Pick": 1,
            "Cards": [_CARD_ID["White Knight"], _CARD_ID["Blue Flyer"]],
        },
        {
            "Pack": 1,
            "Pick": 2,
            "Cards": [_CARD_ID["Black Removal"], _CARD_ID["Red Burn"]],
        },
    ]
    scanner.picked_cards[0] = [_CARD_ID["White Knight"], _CARD_ID["Black Removal"]]


# --- export_draft ------------------------------------------------------------


def test_export_csv_rows_and_picked_flags(env):
    _seed_history(env["scanner"])

    result = tools.export_draft(env["scanner"], "csv")

    assert result.ok
    assert result.format == "csv"
    rows = list(csv.reader(io.StringIO(result.text)))
    header, body = rows[0], rows[1:]
    assert header[:4] == ["Pack", "Pick", "Picked", "Name"]
    assert len(body) == 4
    picked = {r[3]: r[2] for r in body}
    assert picked["White Knight"] == "1"
    assert picked["Blue Flyer"] == "0"
    assert picked["Black Removal"] == "1"
    assert picked["Red Burn"] == "0"


def test_export_json_structure(env):
    _seed_history(env["scanner"])

    result = tools.export_draft(env["scanner"], "json")

    assert result.ok
    payload = json.loads(result.text)
    assert [p["Pick"] for p in payload] == [1, 2]
    first_pack = payload[0]["Cards"]
    assert {c["Name"]: c["Picked"] for c in first_pack} == {
        "White Knight": True,
        "Blue Flyer": False,
    }


def test_export_file_name_uses_event_set(env):
    _seed_history(env["scanner"])

    assert tools.export_draft(env["scanner"], "csv").file_name == "DraftExport_TEST.csv"
    assert (
        tools.export_draft(env["scanner"], "json").file_name == "DraftExport_TEST.json"
    )


def test_export_file_name_without_event_set(env):
    _seed_history(env["scanner"])
    env["scanner"].draft_sets = []

    assert tools.export_draft(env["scanner"], "csv").file_name == "DraftExport.csv"


def test_export_empty_history_rejected(env):
    result = tools.export_draft(env["scanner"], "csv")

    assert not result.ok
    assert "No draft history" in result.message
    assert result.text == ""


def test_export_unknown_format_rejected(env):
    _seed_history(env["scanner"])

    result = tools.export_draft(env["scanner"], "xml")

    assert not result.ok
    assert "Unknown export format" in result.message


def test_export_serializer_failure_reported(env):
    _seed_history(env["scanner"])

    with patch(
        "mtga_bridge.tools.export_draft_to_csv", side_effect=ValueError("boom")
    ):
        result = tools.export_draft(env["scanner"], "csv")

    assert not result.ok
    assert "boom" in result.message


def test_export_snapshots_history_copy(env):
    """The scanner's history is copied under the lock, so a mutation during
    serialization can't shorten the export."""
    _seed_history(env["scanner"])
    real = tools.export_draft_to_json

    def clear_then_serialize(history, dataset, picked):
        env["scanner"].draft_history.clear()
        return real(history, dataset, picked)

    with patch("mtga_bridge.tools.export_draft_to_json", clear_then_serialize):
        result = tools.export_draft(env["scanner"], "json")

    assert len(json.loads(result.text)) == 2


# --- save_text_file ----------------------------------------------------------


def test_save_text_file_writes(env, tmp_path):
    target = tmp_path / "out" / "export.csv"
    target.parent.mkdir()

    ack = tools.save_text_file(str(target), "a,b\n1,2\n")

    assert ack.ok
    assert target.read_text() == "a,b\n1,2\n"
    assert "export.csv" in ack.message


def test_save_text_file_no_path(env):
    ack = tools.save_text_file("", "data")

    assert not ack.ok
    assert "No file selected" in ack.message


def test_save_text_file_unwritable_path(env, tmp_path):
    missing_dir = tmp_path / "does" / "not" / "exist" / "export.csv"

    ack = tools.save_text_file(str(missing_dir), "data")

    assert not ack.ok
    assert "export.csv" in ack.message


# --- locate_mtga_data --------------------------------------------------------


def _make_mtga_data(root, name="MTGA_Data"):
    folder = root / name
    (folder / "Downloads" / "Raw").mkdir(parents=True)
    return folder


def test_locate_mtga_data_accepts_valid_folder(env, tmp_path):
    folder = _make_mtga_data(tmp_path)

    with patch("mtga_bridge.tools.write_configuration") as write:
        result = tools.locate_mtga_data(env["runtime"], str(folder))

    assert result.ok
    assert result.path == str(folder)
    assert env["config"].settings.database_location == str(folder)
    assert env["scanner"].set_data.db_path == str(folder)
    write.assert_called_once()


def test_locate_mtga_data_descends_into_mtga_data(env, tmp_path):
    """Picking MTGA's parent directory should still resolve, as the menu did."""
    parent = tmp_path / "MTGA"
    parent.mkdir()
    folder = _make_mtga_data(parent)

    with patch("mtga_bridge.tools.write_configuration"):
        result = tools.locate_mtga_data(env["runtime"], str(parent))

    assert result.ok
    assert result.path == str(folder)


def test_locate_mtga_data_rejects_folder_without_downloads_raw(env, tmp_path):
    folder = tmp_path / "MTGA_Data"
    folder.mkdir()

    with patch("mtga_bridge.tools.write_configuration") as write:
        result = tools.locate_mtga_data(env["runtime"], str(folder))

    assert not result.ok
    assert "Downloads/Raw" in result.message
    assert env["config"].settings.database_location != str(folder)
    write.assert_not_called()


def test_locate_mtga_data_rejects_empty_selection(env):
    result = tools.locate_mtga_data(env["runtime"], "")

    assert not result.ok
    assert "No folder selected" in result.message


def test_locate_mtga_data_clears_unknown_id_cache(env, tmp_path):
    folder = _make_mtga_data(tmp_path)
    env["scanner"].set_data.unknown_id_cache["999"] = {"name": "stale"}

    with patch("mtga_bridge.tools.write_configuration"):
        tools.locate_mtga_data(env["runtime"], str(folder))

    assert not env["scanner"].set_data.unknown_id_cache


def test_locate_mtga_data_without_scanner(env, tmp_path):
    """Config still persists when the scanner hasn't been built yet."""
    folder = _make_mtga_data(tmp_path)
    env["runtime"].scanner = None

    with patch("mtga_bridge.tools.write_configuration"):
        result = tools.locate_mtga_data(env["runtime"], str(folder))

    assert result.ok
    assert env["config"].settings.database_location == str(folder)


# --- serialization -----------------------------------------------------------


def test_view_models_serialize_camel_case(env):
    _seed_history(env["scanner"])

    export = tools.export_draft(env["scanner"], "csv").model_dump(by_alias=True)
    assert "fileName" in export and "file_name" not in export

    with patch("mtga_bridge.tools.write_configuration"):
        located = tools.locate_mtga_data(
            env["runtime"], str(_make_mtga_data(env["tmp_path"]))
        ).model_dump(by_alias=True)
    assert set(located) == {"ok", "message", "path"}
