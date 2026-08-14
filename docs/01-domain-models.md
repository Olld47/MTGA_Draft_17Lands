# Domain Models & Data Structures

**Purpose:** Defines the core data structures used throughout the application logic.
**Target:** AI Context & Type Definition for Migration/Development.

> Two notation conventions are used deliberately:
> - **Canonical Python shapes** (§1–§4) are snake_case and match the pydantic
>   models in `src/` exactly.
> - **Desktop IPC shapes** (§5–§6) are the wire format the React frontend reads:
>   camelCase, because every bridge model derives from `_VM`
>   (`desktop/src-tauri/src-python/mtga_bridge/viewmodels.py`).

## 1. The Card Object (Canonical)

Every card flowing through the system eventually matches this shape after data merging.

```typescript
type Card = {
  arena_ids: number[] // Array of MTGA GrpIds (handles alt-arts & printings)
  name: string // Sanitized English name
  cmc: number // Base Converted Mana Cost
  mana_cost: string // Raw string (e.g., "{1}{W}{U}")
  types: string[] // Supertypes: ["Creature", "Artifact"]
  colors: string[] // ["W", "U"] (Sorted WUBRG!)
  tags: string[] // Scryfall semantic roles: ["removal", "fixing_ramp"]
  deck_colors: {
    [archetype: string]: {
      gihwr: number // Games in Hand Win Rate (0.0 - 100.0)
      alsa: number // Average Last Seen At (1.0 - 15.0)
      iwd: number // Improvement When Drawn
      samples: number // Sample size for statistical confidence
    }
  }
}
```

## 2. The Statistical Record (17Lands Raw)

Data fetched directly from the 17Lands `card_ratings` API before transformation.

```json
{
  "gihwr": 58.5, // Games in Hand Win Rate
  "ohwr": 56.2, // Opening Hand Win Rate
  "alsa": 2.1, // Average Last Seen At
  "iwd": 5.4, // Improvement When Drawn
  "sample_size": 15000
}
```

## 3. The Draft State (In-Memory)

The mutable state maintained during a draft session by `ArenaScanner`.

```typescript
interface DraftState {
  current_draft_id: string // e.g., UUID from Arena
  event_string: string // "PremierDraft_OTJ_2024..."
  draft_type: number // Enumerator (e.g., 2 for PremierDraft_V2)
  draft_sets: string[] // ["OTJ"]

  current_pack: number // 1, 2, or 3
  current_pick: number // 1 to 15 (or 14)

  pack_cards: string[][] // Matrix of cards currently in packs (for 8 players)
  taken_cards: string[] // Array of Arena IDs (The active Pool)
  picked_cards: string[][] // Matrix tracking exactly what was picked from where

  draft_history: {
    // Used for exporting to CSV/JSON
    Pack: number
    Pick: number
    Cards: string[]
  }[]
}
```

## 4. The Advisor Recommendation

The output of the logic engine sent to the UI, defined by `src/advisor/schema.py`.

```typescript
interface Recommendation {
  card_name: string
  base_win_rate: number
  contextual_score: number // Primary sort key (0-100)
  z_score: number // Statistical advantage vs pack average
  cast_probability: number // 0.0 to 1.0 (Frank Karsten pip math)
  wheel_chance: number // 0.0 to 100.0 (Polynomial probability)
  functional_cmc: number // Adjusted CMC for cost-reduction/alternate casting
  reasoning: string[] // Array of human-readable factors (e.g. ["Critical: Needs Removal"])
  is_elite: boolean // True if card is a game-warping Bomb
  archetype_fit: string // "Neutral", "High", or "Splash/Speculative"
  tags: string[] // Scryfall semantic tags
}
```

---

## 5. The IPC Serialization Boundary (Desktop)

The desktop app crosses the Python <-> JavaScript boundary with pydantic models in `mtga_bridge/viewmodels.py`. Every model derives from a single base:

```python
class _VM(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,   # pack_cards -> packCards
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,    # pytauri serializes with a bare model_dump_json()
    )
```

Two invariants follow from this:

1. **Python fields stay snake_case; the alias does the conversion.** Never rename a field to camelCase to "match" the frontend.
2. **Any `model_dump()` whose keys are consumed by Python** (e.g. `setattr` onto the snake_case `Settings` model in `services.apply_settings_patch`) must pass `by_alias=False` explicitly — the default emits camelCase keys.

## 6. Desktop ViewModels (Wire Format)

The React frontend consumes these camelCase shapes. Field lists below are abbreviated; the source of truth is `viewmodels.py`.

### A. Boot Complete (`boot://complete`)

```typescript
interface BootComplete {
  foundDraft: boolean
  eventSet: string      // e.g. "OTJ"
  eventType: string     // "PremierDraft" | "Sealed" | ...
  pack: number
  pick: number
  hasDataset: boolean
}
```

### B. Draft State (`get_draft_state` -> `DraftStateVM`)

```typescript
interface DraftState {
  booted: boolean
  eventSet: string
  eventType: string
  eventString: string
  draftId: string
  startTime: string | null
  pack: number
  pick: number
  activeFilter: string      // "All Decks"
  filterLabel: string       // "Auto"
  packCards: CardVM[]       // Live pack, each card scored
  missingCards: CardVM[]    // Wheel-tracker cards you passed
  takenCount: number
  draftComplete: boolean    // full pool picked -> Draft tab swaps to recap
  signals: { scores: Record<string, number> }   // WUBRG keys
  poolSummary: PoolSummaryVM | null             // curve, pips, type counts
  datasetName: string | null
  logSource: "live" | "history"
  logName: string
}
```

### C. Card (`CardVM`)

```typescript
interface CardVM {
  name: string
  manaCost: string
  cmc: number
  colors: string[]         // sorted WUBRG
  types: string[]
  rarity: string
  image: string[]          // Scryfall image URIs
  count: number
  stats: CardStatsVM | null   // gihwr/ohwr/gpwr/alsa/ata/iwd/gih/ngp (nullable)
  recommendation: RecommendationVM | null
  isPicked: boolean
  returnableAt: number[]
  tier: string | null      // active tier-list grade
  deckColors: DeckColorVM[]    // per-color play-share for hover
}
```

> `CardVM` is an explicit whitelist, not an auto-projection of `CardData`: fields
> with zero frontend consumers (e.g. `oracle_text`, `subtypes`) are intentionally
> **not** serialized. Add them only when the React app starts rendering them.

### D. Settings (`SettingsVM`)

```typescript
interface Settings {
  deckFilter: string
  filterFormat: string      // "Colors" | "Names"
  resultFormat: string      // "Percentage" | "Rating" | "Grade"
  uiSize: string            // legacy percentage string "40%".."250%"
  desktopTheme: string      // "System" | "Dark" | "Light"
  // + language, alwaysOnTop, cardColorsEnabled, autoSyncDatasets,
  //   updateNotificationsEnabled, draftLogEnabled, missingNotificationsEnabled,
  //   arenaLogLocation, databaseLocation, overlayGeometry, deckMidDistribution ...
}
```

### E. Events (Python -> JS)

| Event | Payload | Purpose |
|---|---|---|
| `boot://progress` | `{message}` | Boot status streamed to the BootScreen |
| `boot://complete` | `BootComplete` | Boot finished; frontend may load state |
| `boot://error` | `{message}` | Fatal boot error |
| `draft://status` | `{text}` | Scanner status text |
| `draft://refresh` | `{seq}` | Frontend re-invokes `get_draft_state` |
| `draft://heartbeat` | `{logMtime, logName}` | Feeds the live status dot |
| `app://error` | `{message}` | Recoverable app error |
| `datasets://updated` | `{updatedCount}` | Background dataset sync finished |
