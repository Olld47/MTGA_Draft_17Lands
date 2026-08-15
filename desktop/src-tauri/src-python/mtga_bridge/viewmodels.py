"""
mtga_bridge.viewmodels
Pydantic models crossing the pytauri IPC boundary. All models serialize with
camelCase aliases so the TypeScript side reads idiomatically.

These modules must stay importable WITHOUT pytauri so the pure logic can be
pytest-ed from the root poetry environment.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _VM(BaseModel):
    # serialize_by_alias — pytauri serializes command returns and Channel
    # messages with a bare `model_dump_json()`, which would otherwise emit the
    # snake_case field names the TypeScript side does not read.
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,
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


class AppError(_VM):
    message: str


class DatasetsUpdatedVM(_VM):
    """Payload for datasets://updated — how many datasets the background check
    actually downloaded. The localized message is built on the frontend
    (i18n owns user-facing text), so this carries only the count."""

    updated_count: int


class DatasetSyncFailedVM(_VM):
    """Payload for datasets://syncFailed — the background dataset sync failed
    (network error, unreachable server). The once-per-day stamp was NOT written,
    so the next launch retries; the frontend shows a localized toast to make the
    failure visible instead of silently serving yesterday's data."""

    pass


class AppUpdateAvailableVM(_VM):
    """Payload for update://available — a newer desktop release exists. The
    frontend builds the localized toast and opens release_url in the OS browser
    (no auto-download)."""

    latest_version: str
    release_url: str


class StatusEvent(_VM):
    text: str


class FrontendErrorBody(_VM):
    """An uncaught JS error forwarded to the Python log. The webview has no
    visible devtools in a bundled build, so this is the only channel."""

    message: str
    source: str = ""  # "boundary" | "onerror" | "unhandledrejection"
    stack: str = ""


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


class DeckColorVM(_VM):
    """One color's play-share stats for the hover ARCHETYPE PLAY SHARE section
    (legacy CardToolTip: colors with GIH WR > 0, sorted by samples, top 10)."""

    color: str
    gihwr: Optional[float] = None
    samples: int = 0


class CardVM(_VM):
    """Bridge projection of one card. Field whitelist is explicit — NOT
    auto-derived from src.card_data.CardData. oracle_text / subtypes exist on
    the Python side but have zero frontend consumers (audited 2026-08), so they
    are intentionally not serialized; add them here only when the React app
    starts rendering card text or subtypes."""

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
    deck_colors: List[DeckColorVM] = []


class SignalsVM(_VM):
    scores: Dict[str, float]  # keys are WUBRG symbols


class PoolSummaryVM(_VM):
    cmc_distribution: List[int]  # 8 buckets
    cmc_average: float = 0.0
    color_pips: Dict[str, int] = {}
    creature_count: int = 0
    noncreature_count: int = 0
    card_count: int = 0
    # Per-type pool counts (Creature/Planeswalker/Battle/Instant/Sorcery/
    # Enchantment/Artifact/Land), basic lands excluded, multiplied by count.
    type_counts: Dict[str, int] = {}


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
    # True once the full pool is picked (legacy dashboard.py draft_complete:
    # taken_count >= expected_total, expected_total from the largest pack seen).
    # The Draft tab then swaps to the recap screen; frontend reads draftComplete.
    draft_complete: bool = False
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
    desktop_theme: str
    # UI language (en/zh) the frontend uses for its localization dictionary.
    language: str
    card_colors_enabled: bool
    draft_log_enabled: bool
    update_notifications_enabled: bool
    missing_notifications_enabled: bool
    auto_sync_datasets: bool
    arena_log_location: str
    database_location: str
    column_configs: Dict[str, List[str]] = {}
    # Per-table column display order (legacy `column_display_orders`): a
    # permutation of the visible configurable fields per view, written by the
    # header drag-to-reorder.
    column_display_orders: Dict[str, List[str]] = {}
    # Per-table sort state (legacy `table_sort_states`): viewId -> {"column",
    # "reverse"}. Restored as the table's initial sort on the next mount.
    table_sort_states: Dict[str, Dict[str, Any]] = {}
    # Pin the main window above other apps (legacy `always_on_top`).
    always_on_top: bool = False
    # Ideal mid-range mana curve for the MANA CURVE panel's dashed overlay.
    deck_mid_distribution: List[int] = []
    # Mini-overlay window geometry as "WxH+X+Y" (logical px), persisted from
    # the legacy CompactOverlay._save_geometry; restored on entering mini mode.
    overlay_geometry: str = "300x600+50+50"


class SettingsPatch(_VM):
    deck_filter: Optional[str] = None
    filter_format: Optional[str] = None
    result_format: Optional[str] = None
    ui_size: Optional[str] = None
    desktop_theme: Optional[str] = None
    language: Optional[str] = None
    card_colors_enabled: Optional[bool] = None
    draft_log_enabled: Optional[bool] = None
    update_notifications_enabled: Optional[bool] = None
    missing_notifications_enabled: Optional[bool] = None
    auto_sync_datasets: Optional[bool] = None
    arena_log_location: Optional[str] = None
    database_location: Optional[str] = None
    column_configs: Optional[Dict[str, List[str]]] = None
    column_display_orders: Optional[Dict[str, List[str]]] = None
    table_sort_states: Optional[Dict[str, Dict[str, Any]]] = None
    always_on_top: Optional[bool] = None
    overlay_geometry: Optional[str] = None


class FilterOptionVM(_VM):
    key: str
    label: str
    win_rate: Optional[float] = None


class FilterOptionsVM(_VM):
    options: List[FilterOptionVM]
    active: str
    auto_detected: str = ""
    auto_detected_label: str = ""


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
    # Dataset freshness for the Datasets-page staleness banner. newest_age_days
    # is the age of the most recently written local dataset file (-1 when no
    # datasets exist); stale is true when that exceeds the bridge's
    # DATASET_STALE_DAYS. last_sync_date is the last SUCCESSFUL auto-sync date
    # (YYYY-MM-DD) — empty when auto-sync never succeeded.
    last_sync_date: str = ""
    newest_age_days: int = -1
    stale: bool = False


class ColorMetricVM(_VM):
    mean: float = 0.0
    std: float = 0.0


class SetMetricsVM(_VM):
    """Mean/std per (win-rate field, color) for the active dataset — the inputs
    the frontend needs to convert raw win rates into Grade/Rating display values
    (a client-side port of src.card_logic.format_win_rate). Keyed
    metrics[field][color]."""

    metrics: Dict[str, Dict[str, ColorMetricVM]] = {}
    has_data: bool = False


class DatasetSwitcherGroupVM(_VM):
    name: str
    path: str


class DatasetSwitcherEventVM(_VM):
    name: str
    groups: List[DatasetSwitcherGroupVM]


class DatasetSwitcherVM(_VM):
    """Event-type → user-group dataset options for the currently detected set,
    plus which (event, group) is loaded. Feeds the masthead switcher (a port of
    top_bar.update_data_sources); selecting one loads that dataset file."""

    set_code: str = ""
    detected_event: Optional[str] = None
    active_event: Optional[str] = None
    active_group: Optional[str] = None
    events: List[DatasetSwitcherEventVM] = []


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
    label: str = ""
    is_live: bool = False


class DraftLogListVM(_VM):
    logs: List[DraftLogVM] = []
    current: str = ""


class DraftExportBody(_VM):
    format: str  # "csv" | "json"


class DraftExportVM(_VM):
    ok: bool = True
    message: str = ""
    text: str = ""
    file_name: str = ""
    format: str = ""


class LocateDataBody(_VM):
    folder: str

class LocateDataVM(_VM):
    ok: bool = True
    message: str = ""
    path: str = ""


class SaveFileBody(_VM):
    path: str
    text: str


class SelectDatasetBody(_VM):
    path: str


class OpenUrlBody(_VM):
    url: str


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
    rarity: str = ""
    mana_cost: str = ""
    gihwr: Optional[float] = None
    row_tag: str = ""
    image: List[str] = []
    # "All Decks" performance for the hover GLOBAL PERFORMANCE block — the same
    # source the legacy CardToolTip reads (`deck_colors["All Decks"]`); the
    # table's GIH WR column keeps the active-filter value above.
    iwd: Optional[float] = None
    alsa: Optional[float] = None
    ata: Optional[float] = None
    samples: Optional[int] = None
    deck_colors: List[DeckColorVM] = []
    tags: List[str] = []


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
# Suggest deck (AI archetype builder)
# ---------------------------------------------------------------------------


class SuggestArchetypeVM(_VM):
    """One candidate deck in the archetype dropdown."""

    label: str
    label_prefix: str = ""
    rating: float = 0.0
    record: str = ""
    colors: List[str] = []
    identity_colors: List[str] = []
    breakdown: str = ""
    main_count: int = 0


class SuggestStateVM(_VM):
    status: str = ""  # empty when a build succeeded; otherwise why it didn't
    is_building: bool = False
    # True when the shown suggestion was built from a pool that no longer
    # matches the scanner's (freshly finished draft, or new picks since build).
    # The frontend auto-triggers a rebuild while this is set.
    stale: bool = False
    archetypes: List[SuggestArchetypeVM] = []
    selected: str = ""
    deck: List[DeckRowVM] = []
    sideboard: List[DeckRowVM] = []
    stats: DeckStatsVM = DeckStatsVM()
    main_count: int = 0
    sideboard_count: int = 0
    breakdown: str = ""
    sim: Optional[SimResultVM] = None
    active_filter: str = "All Decks"


class SuggestProgress(_VM):
    """Streamed over a Channel while suggest_calculate runs."""

    kind: str  # "status" | "variant"
    text: str = ""
    archetype: Optional[SuggestArchetypeVM] = None


class SuggestSelectBody(_VM):
    label: str


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
# Practice pools (random / imported sealed)
# ---------------------------------------------------------------------------


class PracticeSetVM(_VM):
    code: str  # 17Lands code, used to resolve the dataset
    name: str
    label: str  # "Set Name (CODE)"
    is_active: bool = False  # listed in the manifest's active sets


class PracticeSetsVM(_VM):
    sets: List[PracticeSetVM] = []
    default_code: str = ""


class PracticeStartBody(_VM):
    set_code: str
    # None generates six random packs; text imports an MTGA decklist.
    import_text: Optional[str] = None


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
