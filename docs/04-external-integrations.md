# External Integrations & APIs

**Status:** Implementation Spec | **Dependencies:** Managed via `pyproject.toml` (Poetry)

> **Data path summary:** the client's primary card data now comes from the
> **pre-compiled cloud datasets** (§1, downloaded from GitHub Pages), not from
> direct API calls. Direct 17Lands / Scryfall calls remain as the **fallback**
> (§2–§3) and as the engine of the server ETL pipeline. This doc covers both.

## 1. Cloud Datasets (Primary Data Path)

The server ETL pipeline (§5 in `05-server-etl-pipeline.md`) compiles card stats
into `.json.gz` files every day and publishes them to GitHub Pages.

- **Base URL:** `constants.REMOTE_DATASET_BASE_URL` (GitHub Pages).
- **Manifest:** `manifest.json` — lists every dataset key (`SET_FORMAT_GROUP`),
  its filename, and a content `hash`.
- **Report:** `report.json` — pipeline execution summary (used for the live
  dataset schedule page).
- **Client sync:** `src/dataset_updater.py` `DatasetUpdater.sync_datasets`:
  1. Fetches `manifest.json` and `report.json`.
  2. Filters to the draft formats 17Lands currently reports as live.
  3. Downloads only missing/updated files (comparing `hash` against
     `Sets/local_manifest.json`).
  4. Writes with atomic file replacement.
- **Auto-sync cadence:** at most **once per UTC day**, gated by
  `is_auto_synced_today()` (see `00-system-overview.md` §5). Manual downloads
  are unaffected. `sync_datasets` returns a typed `SyncResult`; the once-per-day
  stamp is written only on success, so a failed day is retried on the next
  launch, and a failed background sync surfaces as `datasets://syncFailed`.

The datasets are also what the **server-side** `extract.py`/`transform.py`
produce — the client never scrapes 17Lands directly in normal operation.

## 2. 17Lands.com API (Statistical Data — Fallback)

The application relies on 17Lands for win-rate data. When a cloud dataset is
missing or incomplete, `src/seventeenlands.py` fetches directly as a fallback.

### A. Card Ratings Endpoint

- **URL:** `https://www.17lands.com/card_ratings/data`
- **Method:** GET
- **Parameters:**
  - `expansion`: Set Code (e.g., `OTJ`, `MH3`).
  - `format`: Event Type (e.g., `PremierDraft`).
  - `start_date`: YYYY-MM-DD
  - `end_date`: YYYY-MM-DD
  - `colors`: Optional filter (e.g., `UB`).

### B. Rate Limiting Strategy (CRITICAL)

- **Cache Directory:** Store responses in `Temp/RawCache/`.
- **Naming Convention:** `{set}_{format}_{start}_{end}_{color}_{user}.json`.
- **Staleness Check:** Network fetches are completely bypassed if the file is < 12 Hours old.
- **Throttling:** Sleeps **1.5 seconds** between archetype requests.

## 3. Scryfall API (Metadata Backup & Tag Harvesting)

### A. Community Tags (`otags`)

The app uses the `ScryfallTagger` to harvest community-sourced roles to feed the Compositional Brain.

- **Endpoint:** `https://api.scryfall.com/cards/search?q=set:{SET} ({QUERY})`
- **Queries:** Complex regex combinations (e.g., `otag:removal OR otag:board-wipe`).
- **Cache:** Stored in `Temp/RawCache/{set}_scryfall_tags.json` for 12 hours.
- **Rate Limit:** Strictly enforces a 0.5s backoff to avoid HTTP 429 penalties.

### B. Bulk Resolution

If the local Arena Database fails to resolve an ID, the app sends a bulk query using the `/cards/collection` endpoint in chunks of 75.

## 4. Local MTGA SQLite Database (Zero-Day Fallback)

To ensure the app works seamlessly on Day 1 of a new set release without waiting for 3rd party APIs, it queries local game files.

- **Path:** `MTGA_Data/Downloads/Raw/Raw_CardDatabase_*.sqlite`
- **Logic:** Joins `Cards` with `Localizations_enUS` and `Enums` to instantly resolve numeric `GrpId`s into English card names, CMCs, and Base Types.
- **Custom Installs:** Users can manually map custom installation paths via the UI (**Settings tab -> Locations**, formerly `File -> Locate MTGA Data Folder`).

## 5. GitHub Releases (Self-Update)

Releases ship the **desktop bundles** (tag `v<desktop-version>` from
`desktop/src-tauri/tauri.conf.json` — the single source of the desktop version —
e.g. `v1.0.0`). The desktop app is the only client and the only self-updating
one; the tkinter app — and its update channel — was removed.

### A. Legacy tkinter self-update channel — removed

The tkinter `src/app_update.py` self-update channel was **deleted** on
2026-08-14 (architecture-review issue03). It had become a zombie: it compared
the desktop release tag (`v0.39.0` → `0.39`) against the tkinter
`APPLICATION_VERSION` (`4.19`) with `float(...)`, which can never fire, and the
desktop app owns update notifications (§5.B below). The tkinter UI itself was
removed entirely on 2026-08-15, so no tkinter asset exists or is attached to
releases.

**Version series (how the numbers relate):**

- **root `APPLICATION_VERSION`** (`src/constants/versions.py`): retained only as
  the bootstrap migration marker for `config.settings.last_run_version`; it is
  not a release version and nothing compares it against desktop tags anymore.
- **desktop version**: single source is `desktop/src-tauri/tauri.conf.json` (it
  names the `.dmg`/`.msi`, fills `Info.plist`, drives the release tag). Every
  other desktop literal — including `mtga_bridge/version.py` — is rewritten
  from it by `bump_desktop_version.py` (one command, one input); the guard
  `test_desktop_version_is_consistent_across_manifests` re-verifies each site
  against it.
- **release tag `v<desktop-version>`**: derived from `tauri.conf.json` by
  `publish-release.yml`.

### B. Desktop app

The desktop app's version series (v1.x) has the single source
`desktop/src-tauri/tauri.conf.json`; the runtime literal
`mtga_bridge/version.py` and every other manifest copy are rewritten from it by
`bump_desktop_version.py`. Its bundles (`.dmg`/`.app` on macOS, `.msi`/`.exe`
on Windows) are attached to the release by `publish-release.yml`, with SHA-256
checksums.

On every launch, `app_update_notifier.py` fetches the latest release tag
~3s after boot on a daemon thread. When the tag is newer than the desktop's own
version it emits `update://available`, and the frontend shows a bottom-right
toast with an "Open Releases" link that opens the Releases page in the OS
browser. There is **no auto-download or in-place install** — users grab the new
bundle from the Releases page themselves.

## 6. Security & Compliance Checklist

1. [x] **User Agent:** All HTTP requests include a descriptive User-Agent header (e.g., `MTGADraftTool/5.0 (Contact: repo_url)`).
2. [x] **Read-Only:** The app never attempts to write to MTGA memory or inject inputs. It interacts strictly via `Player.log` and Local SQLite mapping.
3. [x] **Data Minimization:** Logs or deck lists are never uploaded to any server unless the user explicitly exports them.
4. [x] **Checksum Verification:** Every release ships SHA-256 checksums so users can verify downloads (see the README Security section).
