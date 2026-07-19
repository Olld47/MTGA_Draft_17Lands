# MTGA Draft Tool — pytauri desktop app

New Tauri 2 + PyO3 (pytauri) UI for the MTGA Draft Tool. Reuses all draft
logic from the repo-root `src/` package — only the UI layer is new. The
legacy tkinter app (`poetry run python main.py` at the repo root) keeps
working unchanged.

## Architecture

```
Player.log → ArenaScanner ─┐ (src/, shared with tkinter app)
                           │
        DraftOrchestrator ─┤ update_queue
                           ▼
     OrchestratorAdapter (mtga_bridge) ── Tauri events ──► React frontend
                           ▲                                    │
     snapshot.build_draft_state ◄── pyInvoke commands ──────────┘
```

- `src-tauri/src-python/mtga_bridge/` — Python bridge package
  - `paths.py` — pins cwd to the repo root **before** importing `src.*`
    (`src/constants.py` derives Sets/Logs/Temp from `os.getcwd()`)
  - `snapshot.py` — headless port of `AppController.refresh_ui_data`
  - `orchestrator_adapter.py` — drains `update_queue` → `draft://*` events
  - `viewmodels.py` — pydantic IPC models (camelCase aliases)
  - `commands.py` — the pytauri command surface (thin wrappers only)
  - `services.py` / `datasets.py` — pure command implementations
- `src/` (this folder) — Vite + React + TypeScript frontend

Pure modules (`snapshot`, `services`, `datasets`, `runtime`,
`orchestrator_adapter`, `viewmodels`) never import pytauri, so they are
unit-tested from the root test suite: `tests/test_bridge_snapshot.py`.

## Dev setup

Requirements: Rust toolchain, Node 20+, uv.

```bash
cd desktop
uv venv --python 3.13 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ./src-tauri
npm install
VIRTUAL_ENV=$PWD/.venv npm run tauri dev
```

Python edits hot-reload without recompiling Rust. `import pytauri` only works
inside the Tauri process (the Rust binary exports `mtga_bridge.ext_mod` from
memory) — that's why `mtga_bridge/__init__.py` defers all pytauri imports
into `main()`.

## Events and commands

| Event | Payload |
|---|---|
| `boot://progress` | `{message}` |
| `boot://complete` | `{foundDraft, eventSet, eventType, pack, pick, hasDataset}` |
| `boot://error` | `{message}` |
| `draft://status` | `{text}` |
| `draft://refresh` | `{seq}` — frontend re-invokes `get_draft_state` |
| `draft://heartbeat` | `{logMtime, logName}` |
| `app://error` | `{message}` |

Commands: `get_boot_status`, `get_draft_state`, `get_taken_cards`,
`force_reload`, `set_log_file`, `list_draft_logs`, `get_settings`,
`set_settings`, `get_filter_options`, `list_datasets`, `list_available_sets`,
`download_dataset` (Channel-streamed progress), `select_dataset`,
`delete_dataset`.

## Manual smoke checklist

- [ ] `npm run tauri dev` boots to the dashboard (BootScreen streams progress)
- [ ] Appending draft events to Player.log fires `draft://refresh` and the
      pack table updates (Emitter.emit is called from the adapter's worker
      thread — verify no thread-safety warnings in the console)
- [ ] Dataset download shows streaming progress and activates the dataset
- [ ] Settings changes persist to the same config.json the tkinter app reads

## Not yet ported (later phases)

Sealed Studio, Custom Deck builder, Compare, Mini overlay, Tier lists,
Practice dialog, post-draft recap, standalone bundling (`scripts/`).
