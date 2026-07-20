"""
mtga_bridge.viewmodels
Pydantic models crossing the pytauri IPC boundary. All models serialize with
camelCase aliases so the TypeScript side reads idiomatically.

These modules must stay importable WITHOUT pytauri so the pure logic can be
pytest-ed from the root poetry environment.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _VM(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class Ack(_VM):
    ok: bool = True
    message: str = ""


# ---------------------------------------------------------------------------
# Events (Python -> JS payloads)
# ---------------------------------------------------------------------------


class BootProgress(_VM):
    message: str


class BootComplete(_VM):
    found_draft: bool
    event_set: str = ""
    event_type: str = ""
    pack: int = 0
    pick: int = 0
    has_dataset: bool = False


class BootError(_VM):
    message: str


class StatusEvent(_VM):
    text: str


class RefreshEvent(_VM):
    seq: int


class HeartbeatEvent(_VM):
    log_mtime: float
    log_name: str


# ---------------------------------------------------------------------------
# Draft state
# ---------------------------------------------------------------------------


class CardStatsVM(_VM):
    """Stats for one deck-color filter, display-rounded."""

    gihwr: Optional[float] = None
    ohwr: Optional[float] = None
    gpwr: Optional[float] = None
    alsa: Optional[float] = None
    ata: Optional[float] = None
    iwd: Optional[float] = None
    gih: Optional[int] = None
    ngp: Optional[int] = None


class RecommendationVM(_VM):
    """1:1 mirror of src/advisor/schema.py::Recommendation."""

    card_name: str
    base_win_rate: float
    contextual_score: float
    z_score: float
    cast_probability: float
    wheel_chance: float
    functional_cmc: float
    reasoning: List[str]
    is_elite: bool = False
    archetype_fit: str = "Neutral"
    tags: List[str] = []


class CardVM(_VM):
    name: str
    mana_cost: str = ""
    cmc: float = 0.0
    colors: List[str] = []
    types: List[str] = []
    rarity: str = ""
    image: List[str] = []
    count: int = 1
    stats: CardStatsVM = CardStatsVM()
    recommendation: Optional[RecommendationVM] = None
    is_picked: bool = False
    returnable_at: List[int] = []
    tier: Optional[str] = None


class SignalsVM(_VM):
    scores: Dict[str, float]  # keys are WUBRG symbols


class PoolSummaryVM(_VM):
    cmc_distribution: List[int]  # 8 buckets
    cmc_average: float = 0.0
    color_pips: Dict[str, int] = {}
    creature_count: int = 0
    noncreature_count: int = 0
    card_count: int = 0


class DraftStateVM(_VM):
    booted: bool = True
    event_set: str = ""
    event_type: str = ""
    event_string: str = ""
    draft_id: str = ""
    # Display string straight from the scanner, e.g. "6/11/2026 5:10:05 PM"
    start_time: Optional[str] = None
    pack: int = 0
    pick: int = 0
    active_filter: str = "All Decks"
    filter_label: str = "Auto"
    pack_cards: List[CardVM] = []
    missing_cards: List[CardVM] = []
    taken_count: int = 0
    signals: SignalsVM = SignalsVM(scores={})
    pool_summary: Optional[PoolSummaryVM] = None
    dataset_name: Optional[str] = None
    log_source: str = "live"  # "live" | "history"
    log_name: str = ""


class TakenCardsVM(_VM):
    cards: List[CardVM] = []
    pool_summary: PoolSummaryVM
    active_filter: str = "All Decks"


class BootStatusVM(_VM):
    booted: bool
    last_message: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsVM(_VM):
    deck_filter: str
    filter_format: str
    result_format: str
    ui_size: str
    card_colors_enabled: bool
    draft_log_enabled: bool
    update_notifications_enabled: bool
    missing_notifications_enabled: bool
    auto_sync_datasets: bool
    arena_log_location: str
    database_location: str
    column_configs: Dict[str, List[str]] = {}


class SettingsPatch(_VM):
    deck_filter: Optional[str] = None
    filter_format: Optional[str] = None
    result_format: Optional[str] = None
    ui_size: Optional[str] = None
    card_colors_enabled: Optional[bool] = None
    draft_log_enabled: Optional[bool] = None
    update_notifications_enabled: Optional[bool] = None
    missing_notifications_enabled: Optional[bool] = None
    auto_sync_datasets: Optional[bool] = None
    arena_log_location: Optional[str] = None
    database_location: Optional[str] = None
    column_configs: Optional[Dict[str, List[str]]] = None


class FilterOptionsVM(_VM):
    options: List[str]
    active: str
    auto_detected: str = ""


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class DatasetInfoVM(_VM):
    label: str
    path: str
    file_name: str
    size_bytes: int = 0
    modified: float = 0.0
    is_active: bool = False


class DatasetListVM(_VM):
    datasets: List[DatasetInfoVM] = []
    active_dataset: Optional[str] = None


class AvailableSetVM(_VM):
    code: str
    name: str


class AvailableSetsVM(_VM):
    sets: List[AvailableSetVM] = []


class DownloadRequest(_VM):
    set_code: str
    event_type: str = "PremierDraft"
    user_group: str = ""


class DownloadProgress(_VM):
    kind: str  # "status" | "percent"
    text: str = ""
    value: float = 0.0


class DownloadResult(_VM):
    ok: bool
    message: str = ""
    dataset: Optional[DatasetInfoVM] = None


class SetLogFileBody(_VM):
    path: str


class DraftLogVM(_VM):
    path: str
    file_name: str
    modified: float


class DraftLogListVM(_VM):
    logs: List[DraftLogVM] = []
    current: str = ""


class SelectDatasetBody(_VM):
    path: str


class DeleteDatasetBody(_VM):
    path: str


# ---------------------------------------------------------------------------
# Post-draft recap
# ---------------------------------------------------------------------------


class RecapCardVM(_VM):
    name: str
    win_rate: Optional[float] = None


class RecapPickVM(_VM):
    name: str
    pack: int
    pick: int
    reference: float  # ALSA (steals) or ATA (reaches)
    delta: float


class RecapArchetypeVM(_VM):
    name: str
    win_rate: Optional[float] = None


class RecapRoleVM(_VM):
    label: str
    count: int


class RecapVM(_VM):
    has_data: bool = False
    pool_power: float = 0.0
    grade: str = ""
    grade_style: str = ""
    top_23_avg: float = 0.0
    format_avg: float = 0.0
    archetypes: List[RecapArchetypeVM] = []
    best_cards: List[RecapCardVM] = []
    steals: List[RecapPickVM] = []
    reaches: List[RecapPickVM] = []
    tribes: List[RecapRoleVM] = []
    roles: List[RecapRoleVM] = []
    staples: List[RecapCardVM] = []
    non_basic_lands: List[RecapCardVM] = []
    rares: List[RecapCardVM] = []
    cmc_distribution: List[int] = []
    type_counts: Dict[str, int] = {}
    is_sealed: bool = False
    draft_id: str = ""


class DraftRecordVM(_VM):
    found: bool = False
    wins: int = 0
    losses: int = 0
    url: str = ""


class DraftRecordBody(_VM):
    draft_id: str


# ---------------------------------------------------------------------------
# Custom deck builder
# ---------------------------------------------------------------------------


class DeckRowVM(_VM):
    name: str
    count: int = 1
    cmc: float = 0.0
    types: List[str] = []
    colors: List[str] = []
    mana_cost: str = ""
    gihwr: Optional[float] = None
    row_tag: str = ""


class DeckPipVM(_VM):
    symbol: str
    name: str
    count: int


class DeckStatsVM(_VM):
    total_cards: int = 0
    creatures: int = 0
    noncreatures: int = 0
    lands: int = 0
    avg_cmc: float = 0.0
    pips: List[DeckPipVM] = []
    curve: Dict[str, int] = {}  # "1".."6" -> count of non-land cards
    tribes: List[RecapRoleVM] = []
    tags: List[RecapRoleVM] = []
    basics: Dict[str, int] = {}  # basic land name -> count in deck


class SimStatsVM(_VM):
    """1:1 with simulate_deck output percentages."""

    mulligans: float = 0.0
    screw_t3: float = 0.0
    screw_t4: float = 0.0
    flood_t5: float = 0.0
    cast_t2: float = 0.0
    cast_t3: float = 0.0
    cast_t4: float = 0.0
    curve_out: float = 0.0
    removal_t4: float = 0.0
    color_screw_t3: float = 0.0
    avg_hand_size: float = 0.0


class SimResultVM(_VM):
    ok: bool = True
    message: str = ""
    stats: Optional[SimStatsVM] = None
    optimization_note: str = ""
    advice: List[str] = []


class DeckStateVM(_VM):
    deck: List[DeckRowVM] = []
    sideboard: List[DeckRowVM] = []
    stats: DeckStatsVM = DeckStatsVM()
    main_count: int = 0
    sideboard_count: int = 0
    active_filter: str = "All Decks"


class SampleHandVM(_VM):
    cards: List[DeckRowVM] = []
    message: str = ""


class DeckExportVM(_VM):
    text: str = ""


class MoveCardBody(_VM):
    card_name: str
    to_sideboard: bool  # True: deck->sb, False: sb->deck


class BasicLandBody(_VM):
    color_name: str  # "Plains" | "Island" | "Swamp" | "Mountain" | "Forest"


# ---------------------------------------------------------------------------
# Sealed studio
# ---------------------------------------------------------------------------


class SealedVariantVM(_VM):
    name: str
    is_active: bool = False
    main_count: int = 0


class SealedStateVM(_VM):
    has_pool: bool = False
    pool_size: int = 0
    session_id: str = ""
    variants: List[SealedVariantVM] = []
    active_variant: str = ""
    deck: List[DeckRowVM] = []
    sideboard: List[DeckRowVM] = []
    stats: DeckStatsVM = DeckStatsVM()
    main_count: int = 0
    sideboard_count: int = 0
    active_filter: str = "All Decks"


class SealedActionVM(_VM):
    """Result of a sealed mutation: the new state plus an optional message."""

    ok: bool = True
    message: str = ""
    state: SealedStateVM = SealedStateVM()


class SealedMoveBody(_VM):
    card_name: str
    to_sideboard: bool  # True: main->sideboard, False: sideboard->main
    count: int = 1


class SealedVariantBody(_VM):
    name: str
    copy_from: Optional[str] = None


class SealedRenameBody(_VM):
    old_name: str
    new_name: str


class SealedImportBody(_VM):
    text: str


class SealedExportVM(_VM):
    text: str = ""


class SealedDeckTechVM(_VM):
    ok: bool = False
    url: str = ""
    text: str = ""  # MTGA payload, returned so the UI can fall back to clipboard
    message: str = ""


# ---------------------------------------------------------------------------
# Compare workspace
# ---------------------------------------------------------------------------


class CompareStateVM(_VM):
    cards: List[CardVM] = []
    active_filter: str = "All Decks"
    available_names: List[str] = []  # for the search autocomplete


class CompareAddBody(_VM):
    name: str


class CompareRemoveBody(_VM):
    name: str


# ---------------------------------------------------------------------------
# Tier lists
# ---------------------------------------------------------------------------


class TierListEntryVM(_VM):
    set_code: str
    label: str
    date: str
    file_name: str


class TierListsVM(_VM):
    lists: List[TierListEntryVM] = []
    sets: List[str] = []  # distinct set codes for the filter dropdown
    active_filter: str = ""


class TierActionVM(_VM):
    ok: bool = True
    message: str = ""
    lists: TierListsVM = TierListsVM()


class TierImportBody(_VM):
    url: str
    label: str


class TierDeleteBody(_VM):
    file_names: List[str]


class TierFilterBody(_VM):
    set_code: str = ""
