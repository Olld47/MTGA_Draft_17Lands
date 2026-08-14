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
  are unaffected.

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

Releases now ship the **desktop bundles** first (tag `v<desktop-version>` from `desktop/src-tauri/tauri.conf.json`, e.g. `v0.39.0`). The two apps handle updates differently.

### A. Legacy tkinter app (`src/app_update.py`)

- **Endpoint:** `https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest`
- **Asset matching:** because the release's first assets are desktop bundles the
  tkinter app cannot run, `AppUpdate.__process_file_version` picks the asset
  **by name** — `UPDATE_FILENAME` — instead of `assets[0]`:
  - macOS: `MTGA_Draft_Tool_macOS.zip`
  - Linux: `MTGA_Draft_Tool_Linux.tar.gz`
  - Windows: `MTGA_Draft_Tool_Setup.exe`
- **Version compare:** parses the semantic tag (`v4.19` -> `4.19`) and compares
  against `APPLICATION_VERSION` in `src/constants.py`. If the named asset is
  absent (the desktop app has replaced the legacy channel), the update is
  silently skipped.

### B. Desktop app

The desktop app has its **own version series** (v0.x, pinned in
`desktop/src-tauri/src-python/mtga_bridge/version.py`). Its bundles
(`.dmg`/`.app` on macOS, `.msi`/`.exe` on Windows) are attached to the same
release by `publish-release.yml`, with SHA-256 checksums.

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
