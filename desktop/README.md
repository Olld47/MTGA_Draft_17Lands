# MTGA Draft Tool — pytauri desktop app

Tauri 2 + PyO3 (pytauri) desktop UI for the MTGA Draft Tool — the **only**
client. Reuses all draft logic from the repo-root `src/` package. The legacy
tkinter app was removed (2026-08-15); the root `main.py` is a convenience
launcher for the built binary, not a second UI.

## Architecture

```
Player.log → ArenaScanner ─┐ (src/, shared engine)
                           │
        DraftOrchestrator ─┤ update_queue
                           ▼
     OrchestratorAdapter (mtga_bridge) ── Tauri events ──► React frontend
                           ▲                                    │
     snapshot.build_draft_state ◄── pyInvoke commands ──────────┘
```

- `src-tauri/src-python/mtga_bridge/` — Python bridge package
  - `paths.py` — pins cwd and `src` importability **before** importing `src.*`.
    In a source checkout it chdirs to the repo root; in a bundle (no repo root
    above the file) it points `MTGA_DRAFT_BASE_DIR` at the per-user data dir.
  - `snapshot.py` — draft state serialization (headless `AppController`
    replacement)
  - `orchestrator_adapter.py` — drains `update_queue` → `draft://*` events
  - `viewmodels.py` — pydantic IPC models (camelCase aliases)
  - `commands/` — per-feature pytauri command packages (thin wrappers only),
    merged into one `Commands` object by `commands/__init__.py`
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
`delete_dataset`, `get_recap`, `get_draft_record`, the `deck_*` custom-builder
commands, the `sealed_*` studio commands, the `compare_*` commands, the
`*_tier_list` commands, and the `suggest_*` commands (`suggest_calculate`
streams per-archetype build progress over a Channel).

## Manual smoke checklist

- [ ] `npm run tauri dev` boots to the dashboard (BootScreen streams progress)
- [ ] Appending draft events to Player.log fires `draft://refresh` and the
      pack table updates (Emitter.emit is called from the adapter's worker
      thread — verify no thread-safety warnings in the console)
- [ ] Dataset download shows streaming progress and activates the dataset
- [ ] Settings changes persist to `config.json`
- [ ] Suggest tab: "Build decks" streams progress, the dropdown fills with
      archetypes, switching one re-renders the deck/stats/simulation, "Sample
      hand" shows Scryfall art, and "Send to builder" lands the deck on the
      Deck tab
- [ ] Settings → Appearance: all three modes repaint every tab; System follows
      an OS light/dark flip live; relaunching in Light shows no dark flash

## Standalone bundling

```bash
cd desktop
scripts/macos/download-py.sh          # once — fetches python-build-standalone
scripts/macos/build.sh                # → target/bundle-release/bundle/
```

`build.sh` installs `mtga-bridge` **and** the repo-root `mtga-draft-tool`
package (`--no-deps`, so the engine's heavy deps stay out of the embedded
interpreter) into the embedded interpreter, then runs `tauri build` with
`src-tauri/tauri.bundle.json` overlaid — that overlay is what flips
`bundle.active` and maps `pyembed/python` into Resources, so it must never move
into `tauri.conf.json` (it would poison `tauri dev`).

Windows has the same script pair (`scripts/windows/download-py.ps1`,
`build.ps1`), taking the target triple as an optional first argument. CI:
`build-desktop-{macos,windows}.yml` — macOS arm64 and Windows x86_64 — on
`workflow_dispatch`, on a merge to `main`/`master`, **or** on a push to any
`ci/desktop*` branch. That last one exists because dispatch needs the Actions
web UI or `gh`, and because a full Rust + numba build (~15 min a leg) should
not sit on the path of ordinary commits:

```bash
git push origin dev:ci/desktop-win     # runs both legs, no gh required
```

The legs are deliberately **separate runs, not jobs inside
`publish-release.yml`**: `continue-on-error` is not a permitted keyword on a job
that calls a reusable workflow, so a red desktop build would mark an otherwise
successful release run as failed. The bundles are unsigned and the `.msi` has
never been launched on real hardware, so they are built but **not attached to
the Release** — `test_release_artifacts_exclude_the_desktop_bundles` is what
holds that line, and is what to revise when signing lands.

macOS x86_64 and Windows arm64 are absent because `numba` ships no wheel for
either. **Linux is not a supported platform** — the deb/rpm bundling and its
scripts were removed in v0.10, before they were ever built.

## Versioning

The desktop app has its own version series, independent of the root
`APPLICATION_VERSION` (`src/constants/versions.py`), which is retained only as
the bootstrap migration marker for `last_run_version`. The desktop version is
written in **eight literals across seven files** — `package.json`,
`package-lock.json` (twice), `pyproject.toml`, `src-tauri/pyproject.toml`,
`src-tauri/Cargo.toml`, `Cargo.lock`, and `src-tauri/tauri.conf.json`.

Only `tauri.conf.json` reaches a user: it names the `.dmg`/`.msi` and fills
Info.plist. The other seven exist to agree with it. `Cargo.toml`'s
`[workspace.package] version` is **not** one of them — `src-tauri` does not
inherit it, and it stays at `0.1.0`.

Bumping is a single command: `poetry run python bump_desktop_version.py <ver>`
rewrites all eight literals and the topmost `CHANGELOG.md` heading from
`tauri.conf.json` — never hand-edit the manifests.
`test_desktop_version_is_consistent_across_manifests` pins the literals to that
heading. Agreeing-but-stale is the failure it exists to catch: the eight sat at
`0.7.0` for five releases while the changelog moved on, and CI published
bundles named `0.7.0` the whole time. After editing `Cargo.lock` by hand, run
`cargo metadata` to confirm it still parses.

`productName` in `tauri.conf.json` is `mtga-draft-desktop`, not the display
name. The macOS `.app` filename follows it, while the Windows workflow's
artifact check greps for `mtga-draft-desktop.exe`, which follows the Cargo
`[[bin]]` name; `tests/test_desktop_bundle_config.py` pins the two equal so a
rename cannot satisfy one and break the other. The user-visible name lives in
the window title and the in-app `<h1>`.

That same test file holds the rest of the bundling contract — the checks worth
running before spending a CI build: every script path a workflow invokes
resolves, the Rust target triple and the `download-py` argument agree, the two
download scripts pin the same interpreter, and the upload globs cover exactly
the configured bundle targets.

A bundled app writes `Sets/`, `Logs/`, `Temp/`, `Debug/` and `config.json` to
the same per-user directory across installs, so re-installs share datasets and
settings. Override with `MTGA_DRAFT_BASE_DIR`.

## Icons

`src-tauri/icons/` is generated, not hand-drawn — the mark is a fanned pack with
the picked card lifted out in gold, and the palette is lifted from
`src/styles/tokens.css` so the icon and the masthead read as one brand.

```bash
./.venv/bin/python desktop/scripts/make_icons.py   # from the repo root
```

The script draws with PIL rather than an SVG source because the toolchain has no
rasterizer (no rsvg/inkscape/imagemagick); `iconutil` assembles the `.icns`, so
regenerating requires macOS. Edit `render()` and re-run — do not retouch the
PNGs, they are overwritten. `tests/test_desktop_bundle_config.py` asserts every
path in `tauri.conf.json`'s icon list exists at the size its filename claims,
and that the pytauri template artwork has not crept back.

## Theming

System / Dark / Light, chosen on the Settings page. `state/theme.ts` sets
`data-theme` on `<html>`; `styles/tokens.css` holds one color block per palette
and a shared type/metrics block. Everything in `app.css` resolves through those
tokens, so a new palette is a third block and nothing else.

The preference lives in `Settings.desktop_theme` in the shared `config.json`.

`tests/test_desktop_theme_tokens.py` asserts WCAG AA over the pairings `app.css`
renders and that both palettes declare the same tokens. It cannot evaluate
`color-mix()` or alpha, and its pair table is hand-written — it guards the
values, not the CSS.

## Entry point

`poetry run python main.py` at the repo root is a convenience launcher for the
built binary. It locates it via `MTGA_DRAFT_DESKTOP`, the bundled `.app`, or a
cargo build under `desktop/target/`, forwards `-f`/`-d` verbatim, and hands
control over. Without a build it prints build/dev guidance and exits 2 — there
is no fallback UI and no `--ui`/`default_ui` routing. For source development
use `npm run tauri dev` in this directory.
