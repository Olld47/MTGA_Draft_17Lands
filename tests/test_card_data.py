"""
tests/test_card_data.py
Guards for the CardData TypedDict: field names must mirror the DATA_FIELD_*
constants in src/constants.py so the documented card shape can't drift.
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
    constants.DATA_FIELD_CMC,
    constants.DATA_FIELD_DECK_COLORS,
    constants.DATA_FIELD_TAGS,
    constants.DATA_FIELD_RARITY,
    constants.DATA_FIELD_COUNT,
    constants.DATA_FIELD_DISABLED,
    constants.DATA_FIELD_WHEEL,
    constants.DATA_SECTION_IMAGES,
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


def test_card_data_documents_guaranteed_core_fields():
    # Every field a card is guaranteed to carry is present in the shape.
    assert GUARANTEED_CORE <= set(CardData.__annotations__)
