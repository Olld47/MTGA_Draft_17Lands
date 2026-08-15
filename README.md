# MTGA Draft Tool

**English** · [简体中文](README.zh-CN.md)

*This project is a fork of [unrealities/MTGA_Draft_17Lands](https://github.com/unrealities/MTGA_Draft_17Lands). Special thanks to the original author for open-sourcing it.*

Magic: The Gathering Arena draft tool that utilizes 17Lands data.

**This application will automatically support new sets as soon as the sets are released on Arena _and_ the data is available on the [17Lands card ratings](https://www.17lands.com/card_ratings) page.**

**Supported Events:** Premier Draft, Traditional Draft, Quick Draft, Sealed, Traditional Sealed, and Cube.

## Table of Contents

- [Security, Verification & macOS Gatekeeper](#security-verification--macos-gatekeeper)
- [Run Steps: Standalone App (Windows / macOS)](#run-steps-standalone-app-windows--macos)
- [Run Steps: Python (Windows / macOS)](#run-steps-python-windows--macos)
- [Marquee Features](#marquee-features)
- [UI Navigation & Tabs](#ui-navigation--tabs)
- [Settings & Preferences](#settings--preferences)
- [File Locations](#file-locations)
- [Tier Lists (API-Based)](#tier-lists-api-based)
- [Signal Detection (Beta)](#signal-detection-beta)
- [Troubleshooting](#troubleshooting)
- [Development & Documentation](#development--documentation)

---

## The Desktop App

The **PyTauri desktop app** — a native [Tauri 2](https://tauri.app/) window running a React + TypeScript frontend over the shared Python draft engine — is the **only client**. The legacy tkinter UI was removed; there is no source fallback.

|  | Desktop |
|---|---|
| Platforms | macOS (arm64) · Windows (x86_64) |
| UI | React + TypeScript inside Tauri 2 |
| Version series | v1.x (`desktop/src-tauri/tauri.conf.json` — single source) |
| Distribution | `.dmg` / `.app` · `.msi` / `.exe` on Releases |

The root `main.py` is a convenience launcher: it locates the built desktop binary (via the `MTGA_DRAFT_DESKTOP` env var, the bundled `.app` on macOS, or a cargo build under `desktop/target/`), forwards `-f`/`-d`, and hands control over. If no build exists it prints build guidance and exits with code 2 — it never falls back to another UI. For desktop source development use `cd desktop && npm run tauri dev`.

---

## Security, Verification & macOS Gatekeeper

Because this is a free, open-source community project, the application is not signed with a paid Apple Developer Certificate ($100/year). As a result, macOS and Windows SmartScreen will flag the application as an "Unidentified Developer."

To guarantee the integrity of your download, our GitHub Actions pipeline automatically generates a **SHA-256 Checksum** for every release. You can compare the hash of your downloaded file against the checksum listed on the [Releases page](https://github.com/Olld47/MTGA_Draft_17Lands/releases) to verify it has not been maliciously modified.

**Mac Users: Bypassing the "App is Damaged" or "Malware" prompt**
macOS actively quarantines unsigned apps downloaded from the internet. To run the app safely:

1. Open **Terminal** (Command + Space -> "Terminal").
2. Type `xattr -cr ` (make sure to include the space at the end!).
3. Drag and drop the `mtga-draft-desktop.app` from your Applications folder directly into the Terminal window.
4. Press **Enter**. You can now double-click the app to open it normally.

---

## Run Steps: Standalone App (Windows / macOS)

- **Step 1:** Download the latest release for your operating system from the [releases page](https://github.com/Olld47/MTGA_Draft_17Lands/releases).
- **Step 2:** Install/Extract the application:
  - **macOS:** Open the `.dmg` and drag `mtga-draft-desktop.app` to your Applications folder. *(See the Security section above if macOS blocks the app from running).*
  - **Windows:** Run the `.msi` installer (or the `.exe`) to install the app.
- **Step 3:** In MTG Arena, go to **Options -> Account**, and check the **Detailed Logs (Plugin Support)** check box.
- **Step 4:** Launch **MTGA Draft Tool**.
- **Step 5:** The app will automatically sync data for the active Arena events. You can open the **Datasets** tab to manually download historical sets or custom date ranges.
  - *Note: If MTG Arena is installed on a secondary drive/custom folder and dataset downloads fail, open the **Settings** tab -> **Locations** and point the app at your `Player.log` and `MTGA_Data` folder.*
- **Step 6:** Configure the tool through the **Settings** tab.
- **Step 7:** Start a draft or sealed event in MTG Arena!

---

## Run Steps: Python (Windows / macOS)

- **Step 1:** [Download](https://github.com/Olld47/MTGA_Draft_17Lands/archive/refs/heads/main.zip) and unzip the repository.
- **Step 2:** Download and install **Python 3.12**.
- **Step 3:** Confirm that you're running Python 3.12 by opening the terminal and entering `python --version` (or `python3 --version`).
- **Step 4:** Install the Poetry package manager by entering `pip install poetry`.
- **Step 5:** Navigate to the unzipped repository folder in your terminal and install the dependencies by entering `poetry install`.
- **Step 6:**
  - *(Mac Only)* Install web certificates by going to `/Applications/Python 3.12/` and double-clicking the file `Install Certificates.command`.
- **Step 7:** In MTG Arena, go to **Options -> Account**, and check the **Detailed Logs (Plugin Support)** check box.
- **Step 8:** Start the application by opening the terminal and entering:
  ```bash
  poetry run python main.py
  ```
  This is a launcher for the built desktop app: it locates the desktop binary and forwards `-f`/`-d` to it. To run the desktop UI from source during development, see [Building Locally](#building-locally).
- **Step 9:** If the application asks you for the location of the Arena player log, open the **Settings** tab -> **Locations** and select your MTGA `Player.log` file.
- **Step 10:** The app will automatically download 17Lands data for currently active sets in the background.
- **Step 11:** Start your draft in Arena.

---

## Marquee Features

- **Compositional Brain (v5.5):** A custom tactical engine that calculates a 0-100 `VALUE` score for cards in your pack. It dynamically weights raw Z-Score power, color lane commitment, curve needs, and relative wheel probability to suggest optimal picks. Look for the ⭐ symbol for elite "Bomb" picks.
- **AI Monte Carlo Auto-Optimizer:** Click the "Auto-Optimize Deck" button to unleash a background simulation engine that mathematically tests different deck permutations (16 lands vs 17 lands, swapping out clunky 5-drops for efficient 2-drops) across 10,000 simulated games to find the perfect 40-card configuration.
- **Sealed Studio:** A fully interactive drag-and-drop workspace specifically tailored for Sealed deckbuilding. Features an AI Shell Generator that automatically builds the top 3 mathematically optimal deck variants for your specific pool (e.g., Best 2-Color, Greedy Splash, Aggro).
- **Automated Cloud Datasets:** The application uses a custom Cloud ETL Pipeline that compiles and distributes the latest 17Lands telemetry every day. When you open the app, it instantly syncs the data for active Arena events in the background so you never have to manually scrape data again. You can view the live dataset schedule [here](https://unrealities.github.io/MTGA_Draft_17Lands/).
- **Zero-Day Card Recognition:** Alternate art cards and basic lands now instantly display their correct names on release day by dynamically querying your local MTG Arena SQLite database for unknown IDs, completely eliminating the wait for third-party API updates.
- **Mini Mode:** Click the `Mini Mode` button to hide the main dashboard and display a compact, draggable, always-on-top window. Perfect for single-monitor setups or playing seamlessly over the Arena client.
- **Dynamic Columns:** You can customize the columns displayed in any table (Pack, Taken Cards, Compare) by **Right-Clicking the column header**. Add specific 17Lands stats or remove ones you don't need, and drag headers to reorder them. The app remembers your layout automatically.
- **Appearance Themes:** Under the **Settings** tab -> **Appearance**, choose between **System**, **Dark**, or **Light** mode (System follows your OS automatically).
- **Bilingual UI:** The desktop app ships with English and 简体中文 locales — switch languages in the **Settings** tab without restarting.

---

## UI Navigation & Tabs

The application is a Live Dashboard plus several functional workspace tabs:

### Draft Dashboard
- **Advisor Recommendations:** Explains the mathematical reasoning behind the top 3 cards in the current pack.
- **Live Pack:** Displays the cards currently offered to you with their tactical scores.
- **Seen Cards (Wheel Tracker):** Tracks cards you passed previously in the draft.
- **Sidebar:** Contains visual "Open Lane" Signal detection, your current Mana Curve, and your Pool Balance (Creatures/Spells/Lands).

### Application Tabs
- **Taken Cards:** View the cards you have drafted. Features a **"Switch to Visual View"** button to stack your cards into mana curve columns exactly like MTG Arena does.
- **Custom Deck:** A fully interactive deck construction environment combining Auto-Generation and manual Custom building. Features a 1-click **Auto-Optimize** button, an **Auto-Lands** button, and live deck size validation.
- **Suggest Deck:** The AI "Suggest Deck" engine streams per-archetype deck builds for your pool, with stats and Monte Carlo simulation, then sends the winning build to the Custom Deck tab.
- **Sealed Deck:** The Sealed Studio workspace — shown only while a Sealed event is active. Drag-and-drop your pool, generate AI deck shells, and build the top variants.
- **Compare Cards:** Search and add multiple cards to directly compare their stats side-by-side.
- **Tiers:** Import and manage custom tier lists from the 17Lands API.
- **Datasets:** Manage, download, and update 17Lands card data locally. Provides detailed download summaries, including exactly how many MTGA cards were successfully matched with 17Lands telemetry data. Choose a **Time Period** (All Time, Latest Event, Last Week, etc.) to match 17Lands, and use **Clear Set History** to delete old downloaded datasets and re-sync a clean copy if loading slows down.
- **Settings:** All application preferences, data locations, and language settings (see below).

---

## Settings & Preferences

Open the **Settings** tab.

- **Appearance:** Switch the entire UI between **System** (follows your OS), **Dark**, or **Light** mode.
- **UI Size:** Increase or decrease the application text and image sizes globally (from 40% up to 250%). Perfect for smaller laptop displays or massive 4k monitors.
- **Language:** Choose between **English** and **简体中文** — applied immediately, no restart needed.
- **Deck Filter:** Choose the deck filter to display, or **Auto** to let the app track your picks and switch to your confirmed color pair once your lane is identified.
- **Filter Format:** Display color permutations (e.g., UB, BG) or guild/shard names (e.g., Dimir, Golgari).
- **Result Format:** Switch the results for win rate fields (GIHWR, OHWR) between a Percentage (55.0%), a 5-point Rating scale, or Grades (A+ to F).
- **Color-Code Rows:** Colors the background of table rows based on the card's color identity.
- **Always on Top:** Keep the app window above the MTG Arena client.
- **Data:** Toggle automatic dataset syncing, update notifications, draft log creation (records the draft step-by-step in the `./Logs` folder), and missing-dataset notifications.
- **Locations:** Set the MTGA `Player.log` and the local `MTGA_Data` database folder manually (useful for custom/secondary installs).
- **Restore Defaults:** Reset every setting back to its default value.

---

## File Locations

The application stores your settings and data in specific locations to ensure they persist across updates.

### Configuration (`config.json`)
The application looks for the configuration file in the following order:
1. **Local Folder:** If `config.json` exists in the same folder as the application, it is used (Portable Mode).
2. **System User Folder:**
   - **Windows:** `%APPDATA%\MTGA_Draft_Tool\config.json`
   - **Mac:** `~/Library/Application Support/MTGA_Draft_Tool/config.json`

The desktop app stores settings in the same per-user directory across installs, so re-installs read the same datasets and settings. Override it with the `MTGA_DRAFT_BASE_DIR` environment variable.

### Datasets & Logs
- Downloaded card data is stored in the `Sets` folder.
- Custom Tier lists are stored in the `Tier` folder.
- Application debug logs are stored in the `Debug` folder, and draft logs are in the `Logs` folder.

---

## Tier Lists (API-Based)

MTGA_Draft_17Lands features integrated support for downloading and using 17Lands tier lists directly within the application.

1. Go to the **Tiers** tab in the application.
2. Enter the 17Lands tier list URL and a custom label, then click Download.
3. Once downloaded, **Right-Click** the header of any table (like the Live Pack table), go to `Add Column`, and select your new tier list!

---

## Signal Detection (Beta)

This feature attempts to identify "Open Lanes" by analyzing the cards passed to you during the draft.

- **How it works:** The tool scans every pack you see in **Pack 1** and **Pack 3**. It calculates a "Signal Score" for every card based on its quality (GIHWR) and how late you are seeing it compared to its Average Taken At (ATA).
- **The Table:** The "Open Lanes" bar chart in the sidebar sums up these scores. A High Score (20+) typically suggests a very open lane, meaning your neighbors are not drafting that color.

---

## Troubleshooting

### Known Issues
- **Missing cards after restarting Arena:** Arena creates a new log after every restart. The application cannot track cards picked prior to an Arena restart.

### Desyncs & Missed Picks
The application features robust crash-recovery and state persistence. If you close the app mid-draft (or MTG Arena crashes), simply reopening the app will instantly resume your draft exactly where you left off.

If the log file ever severely desyncs, click the **Rescan** button in the top bar. This will wipe the application's current memory, rapidly re-read the entire log file from the beginning, and cleanly reconstruct your draft state.

### Arena Log Issues
If the application cannot detect an active event, open the **Settings** tab -> **Locations** and ensure the proper `Player.log` is selected.

### Custom Installation Folders
If MTG Arena is installed in a non-standard directory (e.g., a secondary Steam library drive), the application might fail to automatically locate the local MTGA card database, causing dataset downloads to fail. To fix this, open the **Settings** tab -> **Locations** and select your custom `MTGA_Data` folder.

---

## Development & Documentation

For developers looking to contribute, fork, or understand the architecture of this application, please refer to the markdown specifications located in the `/docs` directory of this repository:

- `00-system-overview.md`
- `01-domain-models.md`
- `02-log-parsing-rules.md`
- `03-business-logic.md`
- `04-external-integrations.md`
- `05-server-etl-pipeline.md`

### Environment Setup

**Root Python dependencies** (the shared engine, the launcher, and the test suite):

1. **Install Python 3.12**
2. **Install Poetry:** `pip install poetry`
3. **Install Dependencies:**
   ```bash
   poetry install
   ```

**Desktop app development** (requires the Rust toolchain, Node.js 20+, and [uv](https://docs.astral.sh/uv/)):

```bash
cd desktop
uv venv --python 3.13 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ./src-tauri
npm install
VIRTUAL_ENV=$PWD/.venv npm run tauri dev
```

### Running Tests

The repository has two test suites.

Python (root — `tests/` mirrors `src/`), using `pytest` with `pytest-cov`:

```bash
poetry run pytest tests/
poetry run pytest tests/ --cov=src
```

Desktop frontend (Vitest + React Testing Library):

```bash
cd desktop && npm test
```

### Automated Releases & Version Management

Releases are fully automated via GitHub Actions. The pipeline triggers **automatically whenever code is merged into the `master` or `main` branch.** It reads the desktop version from `desktop/src-tauri/tauri.conf.json`, tags the release `v<version>`, builds the **desktop bundles** (macOS arm64 `.dmg` / `.app`, Windows x86_64 `.msi` / `.exe`), and publishes them to the [Releases](https://github.com/Olld47/MTGA_Draft_17Lands/releases) page with SHA-256 checksums and a macOS Gatekeeper note.

The desktop app's version series (v1.x) is read from `desktop/src-tauri/tauri.conf.json` — the single source. **Bumping the desktop version is a single command:** `bump_desktop_version.py <version>` takes `desktop/src-tauri/tauri.conf.json` as the single source and rewrites every desktop manifest literal (`desktop/package.json`, `desktop/package-lock.json`, `desktop/pyproject.toml`, `desktop/src-tauri/pyproject.toml`, `desktop/src-tauri/Cargo.toml`, `desktop/Cargo.lock`, and `mtga_bridge/version.py`) plus the topmost `CHANGELOG.md` heading from that one input — never hand-edit the manifests. The root `APPLICATION_VERSION` (`src/constants/versions.py`) is retained only as the bootstrap migration marker for `last_run_version` and is not part of the desktop release series.

*(If you merge code into main without bumping the version, the pipeline simply rebuilds and re-uploads the bundles on the existing release — perfect for hotfixes.)*

### Building Locally

- **Desktop app:** from the repo root, run `./build_desktop.sh`. It requires `uv`, Node.js/npm, and the Rust toolchain, and produces the bundles under `desktop/target/bundle-release/bundle/`. Supported targets are macOS arm64 and Windows x86_64 — the other combos have no `numba` wheel, and **Linux is not a desktop target**. For day-to-day development use `cd desktop && npm run tauri dev`.
