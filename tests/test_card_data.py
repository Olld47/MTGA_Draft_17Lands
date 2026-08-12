"""
tests/test_card_data.py
Guards for the CardData TypedDict: field names must mirror the DATA_FIELD_*
constants in src/constants.py so the documented card shape can't drift. The
single exception is returnable_at, a computed pack-card field with no
constants.py equivalent — whitelisted below by name.
"""

from src.card_data import CardData
from src import constants

# The subset of DATA_FIELD_* / DATA_SECTION_* constants that describe a card's
# own fields. (The DATA_FIELD_17LANDS_* long keys are 17Lands *API response*
# keys, not card fields, so they are deliberately excluded.)
CARD_FIELD_CONSTANTS = (
    constants.DATA_FIELD_NAME,
    constants.DATA_FIELD_MANA_COST,
    constants.DATA_FIELD_COLORS,
    constants.DATA_FIELD_TYPES,
    constants.DATA_FIELD_SUBTYPES,
    constants.DATA_FIELD_CMC,
    constants.DATA_FIELD_DECK_COLORS,
    constants.DATA_FIELD_TAGS,
    constants.DATA_FIELD_RARITY,
    constants.DATA_FIELD_COUNT,
    constants.DATA_FIELD_DISABLED,
    constants.DATA_FIELD_WHEEL,
    constants.DATA_SECTION_IMAGES,
    constants.DATA_FIELD_ORACLE_TEXT,
)

STAT_FIELD_CONSTANTS = (
    constants.DATA_FIELD_GIHWR,
    constants.DATA_FIELD_OHWR,
    constants.DATA_FIELD_GPWR,
    constants.DATA_FIELD_ALSA,
    constants.DATA_FIELD_IWD,
    constants.DATA_FIELD_ATA,
    constants.DATA_FIELD_NGP,
    constants.DATA_FIELD_NGOH,
    constants.DATA_FIELD_GIH,
    constants.DATA_FIELD_NGND,
    constants.DATA_FIELD_GNSWR,
    constants.DATA_FIELD_GDWR,
    constants.DATA_FIELD_NGD,
)

KNOWN_CARD_FIELDS = set(CARD_FIELD_CONSTANTS + STAT_FIELD_CONSTANTS)

# The one documented magic-string exception: returnable_at is a computed
# pack-card enrichment set by ArenaScanner.retrieve_current_pack_cards (the
# picks at which a card may wheel back), not a dataset field, so it has no
# DATA_FIELD_* constant. Anything ELSE in CardData must map to a constant.
PACK_CARD_FIELD_RETURNABLE_AT = "returnable_at"

KNOWN_CARD_FIELDS.add(PACK_CARD_FIELD_RETURNABLE_AT)

# Fields initialize_card_data() guarantees on every card it touches.
GUARANTEED_CORE = {
    constants.DATA_FIELD_NAME,
    constants.DATA_FIELD_MANA_COST,
    constants.DATA_FIELD_TYPES,
    constants.DATA_FIELD_CMC,
    constants.DATA_FIELD_DECK_COLORS,
}


def test_card_data_fields_all_map_to_constants():
    # No undocumented magic-string field names in the documented card shape.
    assert set(CardData.__annotations__) <= KNOWN_CARD_FIELDS


def test_card_data_documents_all_known_card_fields():
    # Every documented card-field constant appears in the documented shape.
    # Guards the reverse drift: removing a field from CardData must fail here,
    # not silently detach the shape from the constants it mirrors.
    assert KNOWN_CARD_FIELDS <= set(CardData.__annotations__)


def test_card_data_documents_guaranteed_core_fields():
    # Every field a card is guaranteed to carry is present in the shape.
    assert GUARANTEED_CORE <= set(CardData.__annotations__)
