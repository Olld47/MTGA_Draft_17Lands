"""
src/card_data.py
Runtime shape of a card dictionary as produced by ``Dataset.get_data_by_id()``
and consumed by the DraftAdvisor. Field names mirror the ``DATA_FIELD_*``
constants in src/constants.py; see tests/test_card_data.py for the sync guard.
"""

from typing import Dict, List, TypedDict


class CardData(TypedDict, total=False):
    """Shape of one card record.

    ``total=False`` because every key can be absent at runtime: unresolved IDs
    skip ``colors``, basic lands skip ``cmc``, and win-rate stats only exist on
    cards that carry 17Lands data. Consumers keep the defensive ``.get()``
    style (three-level ``deck_colors`` chains), and dirty values (e.g. a
    ``"abc"`` win rate) are still handled at runtime — a TypedDict is purely
    static, with no runtime enforcement.
    """

    name: str
    mana_cost: str
    colors: List[str]
    # Computed pack-card enrichment (only on ArenaScanner.retrieve_current_pack_cards
    # output): the picks at which this card may wheel back. Not a dataset field —
    # no DATA_FIELD_* constant exists; the guard test whitelists it by name.
    returnable_at: List[int]
    types: List[str]
    subtypes: List[str]
    cmc: int
    deck_colors: Dict[str, Dict[str, float]]
    tags: List[str]
    rarity: str
    count: int
    disabled: bool
    image: List[str]
    wheel: float
    # Scryfall oracle text — present for cards in downloaded datasets; absent on
    # synthetic basic-land stubs and locally-resolved zero-day cards.
    oracle_text: str
    # 17Lands win-rate stats (short keys; see DATA_FIELD_17LANDS_DICT in constants)
    gihwr: float
    ohwr: float
    gpwr: float
    alsa: float
    ata: float
    iwd: float
    ngp: float
    ngoh: float
    gih: float
    ngnd: float
    gnswr: float
    gdwr: float
    ngd: float
