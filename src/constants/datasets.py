"""Dataset/remote-pipeline constants: rate limits, URLs, tag visuals,
name corrections. External APIs must never be hit without caching; the
limits here define the pacing."""

SCRYFALL_REQUEST_BACKOFF_DELAY_SECONDS = 5
SCRYFALL_REQUEST_ATTEMPT_MAX = 5

DATASET_DOWNLOAD_RATE_LIMIT_SEC = 60

CARD_RATINGS_BACKOFF_DELAY_SECONDS = 30
CARD_RATINGS_INTER_DELAY_SECONDS = 1
CARD_RATINGS_ATTEMPT_MAX = 5

# --- Remote ETL Pipeline ---
REMOTE_MANIFEST_URL = "https://olld47.github.io/MTGA_Draft_17Lands/manifest.json"
REMOTE_DATASET_BASE_URL = "https://olld47.github.io/MTGA_Draft_17Lands/"
# 17Lands set/format catalog: live_formats_by_expansion names the expansions
# (and formats) currently playable on MTGA — the source of truth for which
# cloud datasets a fresh install should download.
SEVENTEENLANDS_DATA_FILTERS_URL = "https://www.17lands.com/data/filters"

# Map internal Scryfall tags to UI-friendly icons and labels
TAG_VISUALS = {
    "removal": "🎯 Removal",
    "evasion": "🦅 Evasion",
    "card_advantage": "📚 Advantage",
    "fixing_ramp": "🌈 Fixing",  # Changed from 🌱 Mana/Fix
    "fixing": "🌈 Fixing",  # Catch-all in case the internal tag was renamed
    "combat_trick": "⚔️ Trick",
    "enhancement": "🛡️ Enhance",
    "token_maker": "👯 Tokens",
    "lifegain": "💖 Lifegain",
    "mana_sink": "⚙️ Sink",
    "protection": "🛡️ Protect",
    "hate": "🚫 Hate",
}

# Known corrupted mappings returned by 17Lands API
CARD_NAME_CORRECTIONS = {
    "Bespoke B?": "Bespoke Bō",
    "Bespoke B": "Bespoke Bō",
    "Bespoke BÃ´": "Bespoke Bō",
}

__all__ = [
    "SCRYFALL_REQUEST_BACKOFF_DELAY_SECONDS",
    "SCRYFALL_REQUEST_ATTEMPT_MAX",
    "DATASET_DOWNLOAD_RATE_LIMIT_SEC",
    "CARD_RATINGS_BACKOFF_DELAY_SECONDS",
    "CARD_RATINGS_INTER_DELAY_SECONDS",
    "CARD_RATINGS_ATTEMPT_MAX",
    "REMOTE_MANIFEST_URL",
    "REMOTE_DATASET_BASE_URL",
    "SEVENTEENLANDS_DATA_FILTERS_URL",
    "TAG_VISUALS",
    "CARD_NAME_CORRECTIONS",
]
