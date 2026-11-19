# Server ETL Pipeline Specification

## 1. Introduction

The Server ETL (Extract, Transform, Load) Pipeline is a standalone, automated system designed to aggregate Magic: The Gathering card metadata and telemetry. It securely fetches data from Scryfall and 17Lands, standardizes the payloads, and compresses them into `.json.gz` files. 

These compiled datasets are then deployed to a static file host (e.g., GitHub Pages), allowing the MTGA Draft Tool desktop client to download complete, pre-calculated statistical packages instantly without hammering third-party APIs.

## 2. Architecture & Execution Flow

The pipeline executes daily via GitHub Actions. It is strictly schedule-driven, meaning it only spends compute resources updating sets that are currently active on MTG Arena.

> **Status of this section.** The event-scheduling design described here is the
> **upstream target**, not what this branch runs today. This branch still reads a
> hand-maintained `server/calendar.json`; upstream replaced it with
> `server/events.py` (a sourced MTGpile feed) and deleted the repo file. See §5
> for both, and §5F for the migration gap. Read every "is" below as "is, once
> the `events.py` port lands".

```mermaid
graph TD
    A[MTGpile Arena event feed] -->|Fetches + validates as_of freshness| B(server/events.py)
    B -->|Resolves set codes via Scryfall + 17Lands catalogs| A2[(calendar.json)]
    A2 -->|Determines Active Sets| C(server/main.py)
    C -->|1. Extract Metadata| D[Scryfall API]
    C -->|2. Extract Telemetry| E[17Lands API]
    D --> F{Transform & Merge}
    E --> F
    F -->|Inject Format Texture & Baseline Stats| G[In-Memory Payload]
    G -->|3. Load (Compress)| H[Output /build/*.json.gz]
    H --> I[manifest.json]
    H --> J[report.json]
    A2 -->|Published to Pages| K[calendar.json]
```

Note the direction reversal in the upstream design: `calendar.json` becomes a
**pipeline output** (published to GitHub Pages alongside the datasets), not an
input. In this branch it is still an input.

## 3. Module Breakdown

| Module | Function |
| :--- | :--- |
| `config.py` | Centralizes all configuration: API delays, retry logic, WAF cooldowns, and definition of the 26 tracked color archetypes. |
| `events.py` | **(upstream only — absent here)** Resolves MTGpile's announced Arena schedule into supported 17Lands jobs. Owns the feed URL, staleness check, title→format mapping, and set-code resolution. Exports `fetch_event_calendar`, `build_event_calendar`, `get_scheduled_events`. |
| `utils.py` | Houses the `APIClient`. Wraps `requests` with robust exponential backoff, automated HTTP 429/403 (Cloudflare WAF) cooldowns, random anti-bot jitter, and a local `.api_cache` system. |
| `extract.py` | Handles all network requests. Responsible for downloading base card definitions, Scryfall community tags (`otags`), and 17Lands archetype-specific win rates. |
| `transform.py` | The "Data Sanitizer." Merges Scryfall IDs with 17Lands `arena_id`s, guarantees all 26 archetypes are pre-initialized (even if data is missing), and formats the payload exactly to the desktop client's expectations. |
| `load.py` | Writes the final `.json.gz` files using **Atomic Writes** (writing to a `.tmp` file, then utilizing OS-level replacement) to prevent dataset corruption. |
| `validate.py` | Post-transform data-quality checks (§6). Runs on the fully assembled dataset with no extra network calls to catch *silent* extraction failures. A check is `WARNING` (surfaced in the report) or `CRITICAL` (the caller skips saving so the previous good file keeps serving). |
| `report.py` | Generates a highly detailed, professional execution summary detailing pipeline intent, data sizes, network errors, and warehouse state. |
| `mock_ui.py` | Local preview server that serves the built datasets plus the calendar / releases / docs pages from `templates/` — a full offline stand-in for GitHub Pages during development. |

## 4. Caching & Etiquette (Critical)

The pipeline is designed to be highly respectful of community APIs:
- **Scryfall Base Cards:** Cached locally for **7 Days**. (Base set data rarely changes).
- **Scryfall Tags:** Cached locally for **7 Days**.
- **17Lands/Scryfall GET Requests:** Cached transparently by `APIClient` for **12 Hours** using MD5 hashing of the full URL. If the pipeline crashes, rerunning it will instantly bypass previously successful network requests.
- **Throttling:** 17Lands is rate-limited to 1 request per ~5 seconds. Scryfall is rate-limited to 1 request per 200ms.

## 5. Event Management (`server/events.py`)

> **Two states, one section.** This branch still uses a hand-maintained
> `server/calendar.json` (§5F records the gap). Upstream replaced it with
> `server/events.py`, which fetches MTGpile's Arena event feed and resolves it
> into jobs, and deleted the repo file. The design below is upstream's; §5F says
> exactly what this branch is missing.

The pipeline does not guess what to download. Upstream no longer relies on a hand-edited file to know: `server/events.py` fetches MTGpile's Arena event feed and resolves it into jobs.

### A. Source & cadence

- **Feed:** `SOURCE_URL = https://mtgpile.com/api/v1/events/arena/all.json` — MTGpile's compilation of Wizards' published MTG Arena event-schedule articles.
- **Freshness gate:** the feed's `as_of` date must parse and be within `MAX_FEED_AGE_DAYS` (7) days of today — not in the future, not stale. A missing, stale, or future `as_of` **fails the run** (`ValueError`); it does not silently produce an empty schedule.
- **Empty schedule fails:** if no event resolves, `build_event_calendar` raises rather than returning `{}`. A run can therefore no longer "succeed" with nothing to do.

### B. Resolution pipeline

1. **Title → 17Lands format.** `FORMAT_TITLES` maps MTGA display names to 17Lands event types (`"Premier Draft"` → `PremierDraft`, `"Traditional Sealed"` → `TradSealed`, …). Deliberately omitted: ambiguous multi-stage events (Limited Open, championship weekends). A title not in the table is logged and skipped.
2. **Name → set code.** Scryfall `/sets` supplies display names; only names whose code passes the 17Lands `expansions` catalog are accepted. Alchemy codes are resolved against 17Lands via the `Y\d{2}<parent>` pattern rather than guessed from a release year. `SET_NAME_ALIASES` covers names MTGpile spells differently (`duskmourn` → `duskmourn: house of horror`).
3. **Cubes.** `CUBE_TITLES` maps cube displays to their pseudo-codes (`Cube - Powered`, `Cube - Planar`) since they have no Scryfall set.
4. **Format whitelist.** Each mapped format must also appear in the 17Lands `formats` catalog.
5. **Sourced dates required.** An event with a missing/unparseable/unordered date window or no `url` is skipped with a warning — dates are never invented.

Unresolved events are logged and skipped individually; an entirely unresolvable feed fails the run.

### C. Output shape

`calendar.json` is written by `save_calendar()` and deployed to GitHub Pages. This is the same file the website's calendar page reads, and it replaces the old repo-root input.

```json
{
  "as_of": "2026-11-18",
  "source_url": "https://mtgpile.com/api/v1/events/arena/all.json",
  "attribution": "Event schedule from mtgpile.com, compiled from Wizards of the Coast's published MTG Arena event-schedule articles.",
  "events": [
    {
      "set_code": "HOB",
      "formats": ["PremierDraft", "TradDraft"],
      "start_date": "2026-08-11",
      "end_date": "2026-09-29",
      "source_url": "https://..."
    }
  ]
}
```

### D. Selecting today's jobs

`get_scheduled_events(calendar, today)` keeps events whose window contains today, unions their formats per `set_code`, and records the earliest `start_date`. `main.py` then writes those codes into `manifest["active_sets"]` — **this is the single source of truth the client obeys.**

When nothing is active the pipeline saves the manifest with an **empty** `active_sets` (clearing yesterday's live sets while preserving the historical warehouse) and exits. That empty list is the correct, visible signal — it must never be omitted or backfilled with stale codes.

### E. Why this matters

The previous design was a hand-maintained `server/calendar.json`. When nobody added the next event, the file's last `end_date` passed, `get_scheduled_events` returned `{}` every day, the run exited early, and the published `manifest.json` froze at its last `active_sets`. The client then downloaded nothing — while the pipeline still reported success. Fetching a sourced feed, failing on stale feeds, and publishing `active_sets` from the live schedule removes that whole failure mode.

### F. This branch's state, and the gap

**What this branch has today:**

| Piece | State |
| :--- | :--- |
| `server/calendar.json` | Present — hand-maintained input, last `end_date` **2026-09-29** |
| `server/events.py` | **Absent** |
| `save_calendar()` in `load.py` | **Absent** — `calendar.json` is never published |
| `src/dataset_manifest.py` | **Absent** |
| Client scoping | Still filters by 17Lands `live_formats_by_expansion` |

**The consequence, observed 2026-11-18:** every calendar entry had expired, so `get_scheduled_events()` returned `{}`, `main.py` logged *"No active events found… Exiting."* and returned early — while `report.json` still reported `SUCCESS`. `manifest.json` therefore froze with `active_sets: ["HOB"]`. 17Lands meanwhile reported live formats `FRA`/`TRK`/`TDM`/`BLB`, and those set codes have **no datasets in the published manifest** (their `*.gz` URLs 404). The client's live-format filter intersected two disjoint key spaces, selected zero keys, and reported success with 0 downloads — stamping the once-per-day date so it never retried that day.

**Three compounding defects, and where each is addressed:**

1. **Expired hand-maintained calendar** → upstream fixes by sourcing the feed and failing the run on a stale `as_of` (§5A). Not addressed here.
2. **Client infers liveness from a second catalog** → upstream fixes by making the client trust `manifest.active_sets` only. A partial mitigation is in this branch's `sync_datasets` (§5F note below).
3. **"Nothing selected" reported as success** → partially mitigated in this branch: an empty selection now falls back to `active_sets`, then to the whole manifest, instead of silently downloading nothing.

**Partial mitigation already in this branch.** `src/dataset_updater.py` `sync_datasets` keeps the live-format filter, but when the filter selects **zero** keys it falls back to the manifest's `active_sets`, and then to the entire manifest. This prevents a total dry run, but it does **not** fix the root cause — a stale `active_sets` still yields stale datasets. Guarded by `test_sync_datasets_falls_back_to_active_sets_when_live_filter_matches_nothing`.

**To close the gap properly,** port upstream's changes together (they are interdependent): `server/events.py`, `server/main.py` + `server/load.py` (`save_calendar`), `src/dataset_manifest.py`, and the `src/dataset_updater.py` rewrite that drops the live-format filter in favour of `manifest.active_sets`. Upstream also removes `src/bootstrap.py` / `src/boot_sync.py` and the `SyncResult` type, so that rewrite reaches beyond the ETL itself.

## 6. Data-Quality Validation (`validate.py`)

The pipeline runs sanity checks on the **fully assembled dataset** before
publishing. They catch *silent* failures where the pipeline "succeeds" but the
numbers are wrong — e.g. hitting an endpoint that ignores the date range or the
colors filter, which collapses every archetype into a tiny copy of the
`"All Decks"` baseline.

- **Sample size guard:** the most-played card must appear in at least a minimum
  fraction of all games (`MIN_TOP_SAMPLE_RATIO`); a real staple covers tens of
  percent, while the wrong-endpoint bug produced ~0.1%.
- **Per-card checks:** the top sample cards must have plausible `All Decks`
  sample counts; a date-range or filter leak drives them to zero.
- **Outcome:** `WARNING` is surfaced in the report; `CRITICAL` causes the caller
  to **skip saving**, so the previously published good file keeps serving.

## 7. Transform Constraints (The "All Decks" Fallback)

Because 17Lands does not immediately have data for every color pair on Day 1 of a new format, the `transform.py` module strictly enforces a data contract for the Desktop UI:

1. Every card must have an `"All Decks"` archetype.
2. Every card must possess keys for all 26 possible archetypes (e.g., `UB`, `WUBRG`). 
3. If 17Lands did not return data for an archetype, `transform.py` injects a placeholder object with `0.0` values. This prevents the Desktop App from throwing fatal `KeyError` exceptions when a user changes their deck filter in the UI. 
4. The pipeline combines mtga_id (from 17Lands) and arena_ids (from Scryfall) into a single array to ensure Showcase, Retro, and Alternate Art card styles are successfully matched by the local MTG Arena log scanner.

## 8. Local Development

To run the ETL pipeline locally for testing:

1. Ensure your dependencies are installed via `poetry install`.
2. Run the pipeline module: `poetry run python -m server.main`.
3. The compressed datasets and manifest will be output to the local `build/` directory.
4. Preview the result as if it were deployed to GitHub Pages with the mock UI:
   `poetry run python -m server.mock_ui` (serves the built datasets plus the calendar / releases / docs pages).
