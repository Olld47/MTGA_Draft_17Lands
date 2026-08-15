"""Card-level constants: basic lands, types, type-selection filters, rarity."""

BASIC_LANDS = [
    "Island",
    "Mountain",
    "Swamp",
    "Plains",
    "Forest",
    "Snow-Covered Island",
    "Snow-Covered Mountain",
    "Snow-Covered Swamp",
    "Snow-Covered Plains",
    "Snow-Covered Forest",
    "Wastes",
]

CARD_TYPE_CREATURE = "Creature"
CARD_TYPE_PLANESWALKER = "Planeswalker"
CARD_TYPE_INSTANT = "Instant"
CARD_TYPE_SORCERY = "Sorcery"
CARD_TYPE_ENCHANTMENT = "Enchantment"
CARD_TYPE_ARTIFACT = "Artifact"
CARD_TYPE_LAND = "Land"

CARD_TYPE_SELECTION_ALL = "All Cards"
CARD_TYPE_SELECTION_CREATURES = "Creatures"
CARD_TYPE_SELECTION_NONCREATURES = "Noncreatures"
CARD_TYPE_SELECTION_NON_LANDS = "Non-Lands"

CARD_TYPE_DICT = {
    CARD_TYPE_SELECTION_ALL: (
        [
            CARD_TYPE_CREATURE,
            CARD_TYPE_PLANESWALKER,
            CARD_TYPE_INSTANT,
            CARD_TYPE_SORCERY,
            CARD_TYPE_ENCHANTMENT,
            CARD_TYPE_ARTIFACT,
            CARD_TYPE_LAND,
        ],
        True,
        False,
        True,
    ),
    CARD_TYPE_SELECTION_CREATURES: ([CARD_TYPE_CREATURE], True, False, True),
    CARD_TYPE_SELECTION_NONCREATURES: ([CARD_TYPE_CREATURE], False, False, True),
    CARD_TYPE_SELECTION_NON_LANDS: (
        [
            CARD_TYPE_CREATURE,
            CARD_TYPE_PLANESWALKER,
            CARD_TYPE_INSTANT,
            CARD_TYPE_SORCERY,
            CARD_TYPE_ENCHANTMENT,
            CARD_TYPE_ARTIFACT,
        ],
        True,
        False,
        True,
    ),
}

CARD_RARITY_COMMON = "common"
CARD_RARITY_UNCOMMON = "uncommon"
CARD_RARITY_RARE = "rare"
CARD_RARITY_MYTHIC = "mythic"

CARD_RARITY_DICT = {
    1: CARD_RARITY_COMMON,
    2: CARD_RARITY_COMMON,
    3: CARD_RARITY_UNCOMMON,
    4: CARD_RARITY_RARE,
    5: CARD_RARITY_MYTHIC,
}

__all__ = [
    "BASIC_LANDS",
    "CARD_TYPE_CREATURE",
    "CARD_TYPE_PLANESWALKER",
    "CARD_TYPE_INSTANT",
    "CARD_TYPE_SORCERY",
    "CARD_TYPE_ENCHANTMENT",
    "CARD_TYPE_ARTIFACT",
    "CARD_TYPE_LAND",
    "CARD_TYPE_SELECTION_ALL",
    "CARD_TYPE_SELECTION_CREATURES",
    "CARD_TYPE_SELECTION_NONCREATURES",
    "CARD_TYPE_SELECTION_NON_LANDS",
    "CARD_TYPE_DICT",
    "CARD_RARITY_COMMON",
    "CARD_RARITY_UNCOMMON",
    "CARD_RARITY_RARE",
    "CARD_RARITY_MYTHIC",
    "CARD_RARITY_DICT",
]
