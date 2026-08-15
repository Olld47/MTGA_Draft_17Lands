# AI Context: MTGA Draft Tool (Architecture Map)

**Role:** You are an expert Systems Architect maintaining the MTGA Draft Tool — a **PyTauri desktop app** (Tauri 2 + React) that is the **only client**. The legacy tkinter UI was removed (2026-08-15); there is no fallback.
**Goal:** Understand the cross-threading, data normalization, desktop IPC bridge, and pro-level heuristics utilized throughout the MTGA Draft Tool.

> Companion docs: `00-system-overview.md` (architecture), `01-domain-models.md`
> (canonical + IPC data shapes), `02-log-parsing-rules.md` (parsing),
> `03-business-logic.md` (scoring engine), `04-external-integrations.md` (APIs),
> `05-server-etl-pipeline.md` (cloud datasets).

## 0. Test environment (macOS)

- The root `.venv` runs on uv-managed `cpython-3.13.9` (local git-ignored
  `.python-version` pin).
- The Python suite has **no Tcl/Tk dependency**: `tests/conftest.py` holds no
  Tk fixtures, and `tests/test_layering.py` AST-checks that `src/`, the
  `mtga_bridge` package, and root `main.py` never import `tkinter`,
  `ttkbootstrap`, or the deleted `src.ui` package.
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
  - **Desktop:** a React + TypeScript frontend inside a Tauri 2 window, driven by the `mtga_bridge` Python package — `snapshot.py` builds state, `orchestrator_adapter.py` streams `draft://*` events, `viewmodels.py` defines camelCase IPC models. This is the only client.

## 2. Critical Constraints

1. **Rate Limiting:** 17Lands and Scryfall API requests must be cached locally for **12-24 hours**. Direct calls are a fallback; prefer cloud datasets.
2. **Color Normalization:** All color keys must be sorted **WUBRG** (e.g., convert "GW" to "WG"). Failure to do this breaks dictionary lookups.
3. **Thread Safety:** The UI must never block. All intensive parsing and Monte Carlo logic runs on `ThreadPoolExecutors` and sends updates via queues. The desktop app drains the scanner's `update_queue` into Tauri events from the adapter's worker thread.
4. **IPC Serialization:** Every desktop bridge model derives from `_VM` with `serialize_by_alias=True` (camelCase wire format). Python code consuming `model_dump()` must pass `by_alias=False`.
5. **Launcher:** `main.py` is a pure launcher — it never selects or renders a
   UI. It locates the built desktop binary (`MTGA_DRAFT_DESKTOP` env var →
   bundled `.app` → cargo `desktop/target/{release,debug}`), forwards `-f`/`-d`,
   and exits 0; without a build it prints build/dev guidance and exits 2. There
   is no fallback UI and no `--ui`/`default_ui` routing.

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

The tkinter UI (and its `src/ui/styles.py` top-level patches) was removed on
2026-08-15, which also removed the old `importlib.reload` pollution surface.
The remaining guardrails (ticket 10, resolved 2026-08-15):

1. **Never `reload()` real modules** to flip behavior (platform switches
   etc.) — inject the decision point instead.
2. **Test suites must be order-insensitive**: subsets/`--order`/parallel runs
   expose latent pollution that full alphabetical runs hide.
3. **Never add a non-idempotent top-level monkey-patch.**
4. **Layering guard (`tests/test_layering.py`):** AST-based — `src/`, the
   `mtga_bridge` package, and root `main.py` must not import `tkinter`,
   `ttkbootstrap`, or the deleted `src.ui` package. Comments/docstrings that
   merely mention "tkinter" don't trip it — only real import statements do.
5. **Verify root cause empirically** (state dump / breakpoints) before fixing.
