import pytest
import os
import json
from src import constants
from src.set_metrics import SetMetrics
from src.configuration import Configuration, Settings
from src.card_logic import CardResult
from src.dataset import Dataset
from src.tier_list import TierList, Meta, Rating
from unittest.mock import MagicMock, patch
from src.card_logic import export_draft_to_csv, export_draft_to_json
from src.constants import BASE_DIR

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(
    BASE_DIR, "tests", "data", "OTJ_PremierDraft_Data_2024_5_3.json"
)

TEST_TIER_LIST = {
    "TIER0": TierList(
        meta=Meta(collection_date="", label="", set="", version=3),
        ratings={
            "Push // Pull": Rating(rating="C+", comment=""),
            "Etali, Primal Conqueror": Rating(rating="A+", comment=""),
            "Virtue of Persistence": Rating(rating="A+", comment=""),
            "Consign // Oblivion": Rating(rating="C+", comment=""),
            "The Mightstone and Weakstone": Rating(rating="B-", comment=""),
            "Invasion of Gobakhan": Rating(rating="B+", comment=""),
        },
    )
}

TIER_TESTS = [
    ([{"name": "Push // Pull"}], "C+"),
    ([{"name": "Consign // Oblivion"}], "C+"),
    ([{"name": "Etali, Primal Conqueror"}], "A+"),
    ([{"name": "Invasion of Gobakhan"}], "B+"),
    ([{"name": "The Mightstone and Weakstone"}], "B-"),
    ([{"name": "Virtue of Persistence"}], "A+"),
    ([{"name": "Fake Card"}], "NA"),
]

OTJ_GRADE_TESTS = [
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
]


@pytest.fixture(name="card_result", scope="module")
def fixture_card_result():
    return CardResult(SetMetrics(None), TEST_TIER_LIST, Configuration(), 1)


@pytest.fixture(name="otj_premier", scope="module")
def fixture_otj_premier():
    dataset = Dataset()
    dataset.open_file(OTJ_PREMIER_SNAPSHOT)
    set_metrics = SetMetrics(dataset, 2)

    return set_metrics, dataset


# The card data is pulled from the JSON set files downloaded from 17Lands, excluding the fake card
@pytest.mark.parametrize("card_list, expected_tier", TIER_TESTS)
def test_tier_results(card_result, card_list, expected_tier):
    # Go through a list of non-standard cards and confirm that the CardResults class is producing the expected result
    result_list = card_result.return_results(card_list, ["All Decks"], ["TIER0"])

    assert result_list[0]["results"][0] == expected_tier


@pytest.mark.parametrize("card_name, colors, field, expected_grade", OTJ_GRADE_TESTS)
def test_otj_grades(otj_premier, card_name, colors, field, expected_grade):
    metrics, dataset = otj_premier
    data_list = dataset.get_data_by_name([card_name])
    assert data_list

    config = Configuration(
        settings=Settings(result_format=constants.RESULT_FORMAT_GRADE)
    )
    results = CardResult(metrics, None, config, 2)
    card_data = data_list[0]
    result_list = results.return_results([card_data], [colors], [field])

    assert result_list[0]["results"][0] == expected_grade


def test_export_draft_to_csv():
    history = [
        {"Pack": 1, "Pick": 1, "Cards": ["123", "789"]},
    ]

    # Mock Picked Cards (List of lists)
    # Pack 1, Pick 1 was "123"
    picked_cards = [["123"]]

    # Mock Dataset
    mock_dataset = MagicMock()
    # History has ["123", "789"].
    # Call 1: "123" -> returns Card A
    # Call 2: "789" -> returns Card B
    mock_dataset.get_data_by_id.side_effect = [
        [{constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2}],
        [{constants.DATA_FIELD_NAME: "Card B", constants.DATA_FIELD_CMC: 3}],
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    header = lines[0].split(",")

    assert "Picked" in header
    assert len(lines) == 3  # Header + 2 rows

    # Identify row order (iteration order)
    # Since we iterated Cards ["123", "789"], Row 1 is Card A, Row 2 is Card B

    # Row 1 (Card A, ID 123) should be picked (1)
    # CSV format: Pack, Pick, Picked, Name, ...
    row1 = lines[1].split(",")
    assert "Card A" in lines[1]
    assert row1[2] == "1"  # Picked column is index 2

    # Row 2 (Card B, ID 789) should not be picked (0)
    row2 = lines[2].split(",")
    assert "Card B" in lines[2]
    assert row2[2] == "0"


def test_export_draft_to_json():
    history = [{"Pack": 1, "Pick": 1, "Cards": ["123"]}]
    picked_cards = [["123"]]

    mock_dataset = MagicMock()
    mock_dataset.get_data_by_id.return_value = [
        {constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2}
    ]

    json_output = export_draft_to_json(history, mock_dataset, picked_cards)
    data = json.loads(json_output)

    assert data[0]["Cards"][0]["Picked"] == True


def test_card_result_empty_metrics(card_result):
    """Verify CardResult gracefully handles cards missing standard metric keys."""
    # A card lacking 'deck_colors' entirely
    card_data = {"name": "Blank Card", "colors": ["W"]}

    res = card_result.return_results(
        [card_data], ["All Decks"], ["gihwr", "alsa", "colors", "name"]
    )

    assert len(res) == 1

    # 0 is gihwr, 1 is alsa, 2 is colors, 3 is name
    assert res[0]["results"][0] == "-"  # gihwr
    assert res[0]["results"][1] == "-"  # alsa
    assert res[0]["results"][2] == "W"  # colors
    assert res[0]["results"][3] == "Blank Card"  # name


def test_export_draft_to_csv_edge_cases():
    """Verify export handles missing picks, unicode names, and empty stats."""
    history = [{"Pack": 1, "Pick": 1, "Cards": ["999"]}]
    # Picked cards map is empty (user disconnect? parsing error?)
    picked_cards = []

    mock_dataset = MagicMock()
    # Mock a card with unicode and missing stats
    mock_dataset.get_data_by_id.return_value = [
        {
            constants.DATA_FIELD_NAME: "Æther Potion",
            # Missing CMC, Colors, etc.
            constants.DATA_FIELD_DECK_COLORS: {},  # Empty stats
        }
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    assert len(lines) == 2
    row = lines[1].split(",")

    # 1. Picked should be 0 (False) safely
    # CSV Structure: Pack, Pick, Picked, Name, Colors, CMC, Type, GIHWR, ALSA, ATA, IWD
    assert row[2] == "0"

    # 2. Name should be preserved (CSV module handles quotes/encoding)
    assert "Æther Potion" in lines[1]

    # 3. Stats should be empty strings/zeros, not crash
    # IWD is the last column (Index 10)
    assert row[10].strip() == ""


def test_get_functional_cmc_mechanics():
    """Verify the functional CMC parser handles Disguise, Spree, Cost Reduction, and missing data safely."""
    from src.card_logic import get_functional_cmc

    # 1. Disguise / Morph (Should be max 3)
    assert get_functional_cmc({"cmc": 5, "oracle_text": "disguise {2}{G}"}) == 3
    assert get_functional_cmc({"cmc": 4, "oracle_text": "face down as a 2/2"}) == 3

    # 2. General Cost Reduction
    assert (
        get_functional_cmc(
            {"cmc": 8, "oracle_text": "this spell costs {1} and {U} less"}
        )
        == 6
    )
    assert get_functional_cmc({"cmc": 5, "oracle_text": "costs 2 less to cast"}) == 3

    # 3. New Mechanics (Spree, Blitz, Cleave)
    assert (
        get_functional_cmc({"cmc": 6, "oracle_text": "spree"}) == 4
    )  # Reduced by 2 as a baseline for alt-casting
    assert get_functional_cmc({"cmc": 5, "oracle_text": "blitz {1}{R}"}) == 3

    # 4. Empty/Missing Data
    assert get_functional_cmc({}) == 0
    assert get_functional_cmc({"cmc": 2, "oracle_text": None}) == 2


# --- card text normalization --------------------------------------------------

def test_get_oracle_text_normalizes_card_text():
    """get_oracle_text is the single normalized card-text accessor. It lower-cases
    string oracle text and falls back to \"\" — without raising — for cards with
    no usable text (missing, None, empty, or non-string)."""
    from src.card_logic import get_oracle_text

    # String text -> lower-cased, otherwise untouched
    assert (
        get_oracle_text({"oracle_text": "Lightning Bolt deals 3 damage."})
        == "lightning bolt deals 3 damage."
    )
    assert get_oracle_text({"oracle_text": "  Mixed CASE  "}) == "  mixed case  "
    # Missing key, None, empty, and non-string values -> "" (never raise)
    assert get_oracle_text({}) == ""
    assert get_oracle_text({"oracle_text": None}) == ""
    assert get_oracle_text({"oracle_text": ""}) == ""
    assert get_oracle_text({"oracle_text": 123}) == ""


# --- deck filter labels ------------------------------------------------------


def test_filter_display_name_uses_the_guild_name_under_the_names_format():
    from src.card_logic import filter_display_name

    assert (
        filter_display_name("WU", constants.DECK_FILTER_FORMAT_NAMES) == "Azorius"
    )
    assert filter_display_name("WU", constants.DECK_FILTER_FORMAT_COLORS) == "WU"


def test_filter_display_name_passes_through_keys_with_no_guild_name():
    """Auto and All Decks are in DECK_FILTERS but not COLOR_NAMES_DICT, so the
    Names format has to fall back to the key rather than to an empty string."""
    from src.card_logic import filter_display_name

    for key in (constants.FILTER_OPTION_AUTO, constants.FILTER_OPTION_ALL_DECKS):
        assert filter_display_name(key, constants.DECK_FILTER_FORMAT_NAMES) == key


def test_filter_win_rate_distinguishes_absent_from_zero():
    """None means 17Lands reported nothing; 0.0 is a real (terrible) rate. The
    UI branches on the difference, so they must not collapse."""
    from src.card_logic import filter_win_rate

    assert filter_win_rate("WU", {"WU": 0.0}) == 0.0
    assert filter_win_rate("UB", {"WU": 56.3}) is None
    assert filter_win_rate("WU", {}) is None
    assert filter_win_rate("WU", None) is None


def test_format_filter_label_appends_the_rate_only_when_present():
    from src.card_logic import format_filter_label

    ratings = {"WU": 56.3}
    assert (
        format_filter_label("WU", constants.DECK_FILTER_FORMAT_NAMES, ratings)
        == "Azorius (56.3%)"
    )
    assert (
        format_filter_label("WU", constants.DECK_FILTER_FORMAT_COLORS, ratings)
        == "WU (56.3%)"
    )
    assert (
        format_filter_label("UB", constants.DECK_FILTER_FORMAT_COLORS, ratings) == "UB"
    )


def test_deck_filter_stats_falls_back_to_all_decks_when_archetype_has_no_games():
    """A card with zero games in the active archetype (samples 0) must not
    render its placeholder 0.0 rates when 17Lands has real numbers under
    All Decks — the "data exists but the tool shows 0" bug."""
    from src.card_logic import deck_filter_stats

    card = {
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {"gihwr": 61.0, "samples": 4000},
            "WU": {"gihwr": 0.0, "samples": 0},  # never played in WU decks
        }
    }
    assert deck_filter_stats(card, "WU")["gihwr"] == 61.0


def test_deck_filter_stats_keeps_the_active_filter_once_it_has_games():
    """samples > 0 means the rate is real — a genuine 0% must stay 0%, and a
    populated lane must not be masked by the broad All Decks aggregate."""
    from src.card_logic import deck_filter_stats

    card = {
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {"gihwr": 55.0, "samples": 4000},
            "WU": {"gihwr": 0.0, "samples": 300},  # a real 0% from actual games
        }
    }
    assert deck_filter_stats(card, "WU")["gihwr"] == 0.0
    assert deck_filter_stats(card, "All Decks")["gihwr"] == 55.0


def test_deck_filter_stats_does_not_invent_data():
    """When neither lane has games the placeholder lane is returned untouched —
    the caller decides how to render a card with no data anywhere."""
    from src.card_logic import deck_filter_stats

    card = {
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {"gihwr": 0.0, "samples": 0},
            "WU": {"gihwr": 0.0, "samples": 0},
        }
    }
    assert deck_filter_stats(card, "WU")["gihwr"] == 0.0
    assert deck_filter_stats(card, "BG") == {}


# --- card_logic ↔ deck_builder circular import -------------------------------


def test_deck_builder_imports_standalone_without_card_logic():
    """Acceptance for the P1 fix: importing deck_builder first (before
    card_logic) must succeed. It used to raise ImportError because card_logic
    eagerly re-exported deck_builder symbols at module scope. Run in a fresh
    interpreter because pytest already holds both modules in sys.modules."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import src.advisor.deck_builder"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_card_logic_no_longer_re_exports_deck_builder_symbols():
    """card_logic must not carry the deck-layer symbols at all — importing them
    here both reintroduces the cycle and hides their true home. Import the names
    from src.advisor.deck_builder directly."""
    import src.card_logic as card_logic

    for name in (
        "suggest_deck",
        "optimize_deck",
        "clear_deck_cache",
        "get_sideboard",
        "GLOBAL_DECK_CACHE",
        "build_variant_consistency",
        "build_variant_greedy",
        "build_variant_curve",
        "build_variant_soup",
    ):
        assert not hasattr(card_logic, name), (
            f"src.card_logic re-exports {name}; import it from "
            "src.advisor.deck_builder instead"
        )


# --- card_logic ↔ advisor-layer circular import ------------------------------

# Every advisor symbol card_logic used to re-export at module scope (simulator /
# deck_scorer / mana_base), and their true homes. The standalone-import tests
# below are run in a fresh interpreter because pytest already holds both
# card_logic and the advisor modules in sys.modules, which would mask the cycle.
_ADVISOR_RE_EXPORTED = (
    # src.advisor.simulator
    "simulate_deck",
    # src.advisor.mana_base
    "calculate_dynamic_mana_base",
    "create_basic_lands",
    "is_castable",
    "ManaSourceAnalyzer",
    "count_fixing",
    "get_strict_colors",
    "select_useful_lands",
    # src.advisor.deck_scorer
    "TIER_TO_GIHWR",
    "get_card_rating",
    "identify_top_pairs",
    "calculate_holistic_score",
    "estimate_record",
)


def _fresh_interpreter_ok(statement):
    """Runs `statement` in a fresh interpreter at the repo root. Returns False
    when the interpreter exits non-zero (the statement raised)."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stderr


def test_simulator_imports_standalone_without_card_logic():
    """Importing simulator first (before card_logic) used to raise ImportError:
    card_logic eagerly re-imported simulate_deck at module scope while simulator
    was still initializing, mid-way through its own import of card_logic."""
    ok, stderr = _fresh_interpreter_ok("import src.advisor.simulator")
    assert ok, stderr


def test_deck_scorer_imports_standalone_without_card_logic():
    """Same import-order fragility for deck_scorer: importing it first used to
    raise ImportError on the re-exported TIER_TO_GIHWR block."""
    ok, stderr = _fresh_interpreter_ok("import src.advisor.deck_scorer")
    assert ok, stderr


def test_mana_base_imports_standalone_without_card_logic():
    """mana_base has no card_logic dependency of its own, but its symbols were
    re-exported by card_logic all the same — importing it first must work and
    never pull card_logic's re-export hub back in."""
    ok, stderr = _fresh_interpreter_ok("import src.advisor.mana_base")
    assert ok, stderr


def test_card_logic_no_longer_re_exports_advisor_symbols():
    """card_logic must not carry any simulator / deck_scorer / mana_base symbol.
    Re-adding one here both reintroduces the import-order cycle and hides the
    symbol's true home. Import them from src.advisor.<module> directly."""
    import src.card_logic as card_logic

    for name in _ADVISOR_RE_EXPORTED:
        assert not hasattr(card_logic, name), (
            f"src.card_logic re-exports {name}; import it from its real "
            "advisor module instead"
        )


def test_card_logic_does_not_transitively_import_advisor_layer():
    """Importing card_logic alone must not drag the advisor layer (numba, deck
    scoring, simulation) into the interpreter. card_logic's own one use of this
    block (identify_top_pairs in filter_options) must be function-local."""
    statement = (
        "import src.card_logic, sys\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('src.advisor'))\n"
        "assert not leaked, leaked"
    )
    ok, stderr = _fresh_interpreter_ok(statement)
    assert ok, stderr


def test_card_text_access_uses_shared_helper():
    """No advisor / card-logic module may inline the lowercased-oracle_text
    access. Everyone calls get_oracle_text() so normalization has a single
    definition and one place to adjust when the card shape changes."""
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    targets = [
        repo_root / "src" / "card_logic.py",
        repo_root / "src" / "sealed_logic.py",
        *sorted((repo_root / "src" / "advisor").glob("*.py")),
    ]
    pattern = re.compile(r'get\("oracle_text",\s*""\)+\.lower\(\)')
    offenders = {}
    for path in targets:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.setdefault(str(path), []).append(lineno)
    assert not offenders, (
        "inline lowercased-oracle_text access still present; use "
        f"src.card_logic.get_oracle_text instead: {offenders}"
    )


def test_no_call_site_stringifies_oracle_text_to_none():
    """No advisor / card-logic module may wrap a raw oracle_text dict access in
    str(). A None oracle_text stringifies to \"None\" — lower-cased \"none\" —
    the exact regression get_oracle_text's empty-string fallback was built to
    prevent. Everyone routes through get_oracle_text."""
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    targets = [
        repo_root / "src" / "card_logic.py",
        repo_root / "src" / "sealed_logic.py",
        *sorted((repo_root / "src" / "advisor").glob("*.py")),
    ]
    pattern = re.compile(r'str\(\s*[^)]*\bget\("oracle_text"')
    offenders = {}
    for path in targets:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.setdefault(str(path), []).append(lineno)
    assert not offenders, (
        "raw oracle_text access stringified with str() (None -> \"none\"); use "
        f"src.card_logic.get_oracle_text instead: {offenders}"
    )
