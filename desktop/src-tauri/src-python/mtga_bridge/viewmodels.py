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
