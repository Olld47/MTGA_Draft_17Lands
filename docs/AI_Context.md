# AI Context: MTGA Draft Tool (Architecture Map)

**Role:** You are an expert Systems Architect maintaining a sophisticated Python/Tkinter application.
**Goal:** Understand the cross-threading, data normalization, and pro-level heuristics utilized throughout the MTGA Draft Tool.

## 1. System Architecture

The application is a **Reactive Overlay & Data Warehouse** for Magic: The Gathering Arena (MTGA).

- **Input:** Tails `Player.log` (UTF-8) on a background thread (`ArenaScanner`).
- **Zero-Day Resolution:** Joins local MTGA SQLite DB tables to resolve internal `GrpId`s to English card names before 17Lands updates.
- **State:** Tracks Draft Pack, Missing Wheel Cards, and Taken Pool via persistent JSON state memory.
- **Output:** Renders a floating UI table ranking cards by a contextual "Score" (0-100), and provides a Monte Carlo simulation engine and Sealed Studio for deck optimization.

## 2. Critical Constraints

1. **Rate Limiting:** 17Lands and Scryfall API requests must be cached locally for **12-24 hours**.
2. **Color Normalization:** All color keys must be sorted **WUBRG** (e.g., convert "GW" to "WG"). Failure to do this breaks dictionary lookups.
3. **Thread Safety:** The UI must never block. All intensive parsing and Monte Carlo logic runs on `ThreadPoolExecutors` and sends updates via queues/`after()` calls.

## 3. Data Schema (Types)

```typescript
// The fundamental unit of data after all APIs and DBs merge
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
