"""Mana fixing heuristics.

Substrings to search for in card oracle text (Case Insensitive), plus cards
whose NAME marks them as fixers.
"""

FIXING_KEYWORDS = [
    # Direct Production (Any Color)
    "mana of any color",
    "mana of any one color",
    "mana of any type",
    "mana of the chosen color",
    # "Choose a color" usually implies fixing (e.g. Thriving lands, Unknown Shores)
    "choose a color",
    # Fetching / Tutoring
    "search your library for a land card",
    "search your library for a basic land",
    "search your library for a land",
    "search your library for a plains",
    "search your library for an island",
    "search your library for a swamp",
    "search your library for a mountain",
    "search your library for a forest",
    "search your library for up to two basic land cards",
    "search your library for up to X basic land cards",
    "basic landcycling",
    "plainscycling",
    "islandcycling",
    "swampcycling",
    "mountaincycling",
    "forestcycling",
    # Token Generation (Treasure/Gold)
    "create a treasure",
    "create x treasure",
    "create a gold token",
    # Enchantments
    "whenever enchanted land is tapped for mana, its controller adds an additional one mana of any color",
]

# Cards with these strings in their NAME are likely fixers.
FIXING_NAMES = [
    "riveteers overlook",
    "brokers hideout",
    "cabaretti courtyard",
    "maestros theater",
    "obscura storefront",
    "great hall",
    "cactus preserve",
    "guild globe",
    "omenpath journey",
]

__all__ = ["FIXING_KEYWORDS", "FIXING_NAMES"]
