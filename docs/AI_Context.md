# AI Context: MTGA Draft Tool (Architecture Map)

**Role:** You are an expert Systems Architect maintaining a dual-UI MTGA Draft Tool: a **PyTauri desktop app** (Tauri 2 + React, default) and a **legacy tkinter app**. Both share the same Python engine (`src/`).
**Goal:** Understand the cross-threading, data normalization, desktop IPC bridge, and pro-level heuristics utilized throughout the MTGA Draft Tool.

> Companion docs: `00-system-overview.md` (architecture), `01-domain-models.md`
> (canonical + IPC data shapes), `02-log-parsing-rules.md` (parsing),
> `03-business-logic.md` (scoring engine), `04-external-integrations.md` (APIs),
> `05-server-etl-pipeline.md` (cloud datasets).

## 0. Test environment (macOS)

- The root `.venv` runs on uv-managed `cpython-3.13.9` (local git-ignored
  `.python-version` pin). Never re-point it at uv's rolling `cpython-3.13`
  build — it ships no Tcl scripts, so the pytest `session_tk_root` fixture
  dies with `TclError` at collection.
- After any `uv venv` rebuild run `./repair_venv_tcl.sh` (idempotent):
  re-points the venv at 3.13.9 AND symlinks its `lib/tcl8.6` + `lib/tk8.6`
  into `.venv/lib` (a venv's `sys.prefix` points at itself, so swapping the
  interpreter alone leaves Tcl unfindable).
- Poetry 2.x lives inside the venv (`.venv/bin/poetry`); `poetry run` auto-
  detects the active environment — no `poetry.toml` needed. Equivalent:
  `poetry run pytest tests/` = `.venv/bin/python -m pytest tests/`.
- Full detail: CLAUDE.md → "Test environment (macOS, uv-managed venv)".

## 1. System Architecture

The application is a **Reactive Overlay & Data Warehouse** for Magic: The Gathering Arena (MTGA).

- **Input:** Tails `Player.log` (UTF-8) on a background thread (`ArenaScanner`).
- **Zero-Day Resolution:** Joins local MTGA SQLite DB tables to resolve internal `GrpId`s to English card names before 17Lands updates.
- **State:** Tracks Draft Pack, Missing Wheel Cards, and Taken Pool via persistent JSON state memory (`Temp/active_draft_state.json`).
- **Data:** Primary card stats come from pre-compiled cloud datasets (GitHub Pages) synced at most once per UTC day; direct 17Lands/Scryfall calls are the fallback.
- **Output:**
  - **Desktop (default):** a React + TypeScript frontend inside a Tauri 2 window, driven by the `mtga_bridge` Python package — `snapshot.py` builds state, `orchestrator_adapter.py` streams `draft://*` events, `viewmodels.py` defines camelCase IPC models.
  - **Legacy:** a tkinter UI ranking cards by a contextual "Score" (0-100), with a Monte Carlo simulation engine and Sealed Studio.

## 2. Critical Constraints

1. **Rate Limiting:** 17Lands and Scryfall API requests must be cached locally for **12-24 hours**. Direct calls are a fallback; prefer cloud datasets.
2. **Color Normalization:** All color keys must be sorted **WUBRG** (e.g., convert "GW" to "WG"). Failure to do this breaks dictionary lookups.
3. **Thread Safety:** The UI must never block. All intensive parsing and Monte Carlo logic runs on `ThreadPoolExecutors` and sends updates via queues. The desktop app drains the scanner's `update_queue` into Tauri events from the adapter's worker thread.
4. **IPC Serialization:** Every desktop bridge model derives from `_VM` with `serialize_by_alias=True` (camelCase wire format). Python code consuming `model_dump()` must pass `by_alias=False`.
5. **UI Dispatch:** `main.py` prefers `--ui` flags, then the `default_ui` config key (default `desktop`); a missing desktop build falls back to tkinter (explicit `--ui desktop` exits with code 2 instead).

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

For the desktop wire format (camelCase `CardVM`, `DraftStateVM`, `SettingsVM`,
the `_VM` alias rules, and the `boot://` / `draft://` / `app://` event payloads),
see `01-domain-models.md` §5–§6.

## 4. Test pollution & module side-effect guardrails

`importlib.reload` re-runs a module body in the **same globals dict** — any
module that monkey-patches at top level (e.g. `src/ui/styles.py` wrapping
`tkinter.ttk.Style.element_create`) becomes self-referential after the second
reload, and any later ttk widget creation hits `RecursionError`. The suite
only stayed green by alphabetical luck (`test_app_layout` < `test_styles`).
Ticket 10 (resolved 2026-08-15) rules:

1. **Top-level monkey-patches must be idempotent** and resolve the genuine
   target **lazily per call** from the live class attribute — see
   `_install_element_create_patch()` / `_resolve_real_element_create()` in
   `src/ui/styles.py`. Never capture the "original" at module-body time on a
   reloadable module (marker-attribute guard skips re-wrapping).
2. **Tests must NOT `reload()` real modules** to flip behavior (platform
   switches etc.) — inject the decision point instead. The two existing
   `test_macos/windows_font_stability` reloads are legacy debt; no new
   reloads.
3. **Test suites must be order-insensitive**: subsets/`--order`/parallel runs
   expose latent pollution that full alphabetical runs hide. Any top-level
   side effect ships with a regression test that reloads the module twice and
   proves the patched symbol still resolves to the genuine implementation
   (see `test_reload_does_not_stack_element_create_wrapper`).
4. **Verify root cause empirically** (state dump / breakpoints) before fixing:
   the ticket's MagicMock-conjecture was wrong — two plain reloads sufficed.
