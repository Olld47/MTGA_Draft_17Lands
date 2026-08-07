import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getSealedState,
  sealedAddBasic,
  sealedAutoGenerate,
  sealedAutoLands,
  sealedClearDeck,
  sealedCreateVariant,
  sealedDeleteVariant,
  sealedExport,
  sealedExportSealeddeck,
  sealedImportDeck,
  sealedMoveCard,
  sealedReloadPool,
  sealedRemoveBasic,
  sealedRenameVariant,
  sealedSelectVariant,
} from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { SealedAction, SealedState } from "../../api/types";
import { DeckStatsView, DeckTable } from "../deck/DeckStatsView";
import { PracticeDialog } from "../practice/PracticeDialog";
import type { GroupBy } from "../../components/cardGroups";

const BASICS = ["Plains", "Island", "Swamp", "Mountain", "Forest"];

/** Type + color visibility for the pool filter bar, mirroring legacy
 *  sealed_studio's filter_vars (creatures/spells/lands + WUBRG + C/M). */
interface PoolFilter {
  creatures: boolean;
  spells: boolean;
  lands: boolean;
  W: boolean;
  U: boolean;
  B: boolean;
  R: boolean;
  G: boolean;
  C: boolean;
  M: boolean;
}

const POOL_FILTER_TYPES = ["creatures", "spells", "lands"] as const;
const POOL_FILTER_COLORS = ["W", "U", "B", "R", "G", "C", "M"] as const;

export function SealedPage({ colorTint }: { colorTint: boolean }) {
  const [state, setState] = useState<SealedState | null>(null);
  const [message, setMessage] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [practiceOpen, setPracticeOpen] = useState(false);
  // Group-by modes, matching the legacy sealed_studio defaults: the pool groups
  // by Color, the built deck by CMC (sealed_studio.py:87-88).
  const [poolGroup, setPoolGroup] = useState<GroupBy | null>("color");
  const [deckGroup, setDeckGroup] = useState<GroupBy | null>("cmc");
  const [poolFilter, setPoolFilter] = useState<PoolFilter>({
    creatures: true,
    spells: true,
    lands: true,
    W: true,
    U: true,
    B: true,
    R: true,
    G: true,
    C: true,
    M: true,
  });

  // The pool table's rows are the sideboard (cards not in the main deck). Apply
  // the filter bar's type + color checkboxes the same way legacy sealed_studio
  // filtered: a card passes the type gate (creature/spell/land), then the color
  // gate (multicolor→M, colorless→C, otherwise its single color).
  const filteredPool = useMemo(() => {
    const pool = state?.sideboard ?? [];
    const { creatures, spells, lands, ...colors } = poolFilter;
    return pool.filter((c) => {
      const isCreature = c.types.includes("Creature");
      const isLand = c.types.includes("Land");
      if (isCreature && !creatures) return false;
      if (isLand && !lands) return false;
      if (!isCreature && !isLand && !spells) return false;
      if (c.colors.length > 1) return colors.M;
      if (c.colors.length === 0) return colors.C;
      return colors[c.colors[0] as keyof typeof colors];
    });
  }, [state, poolFilter]);

  const filteredPoolCount = filteredPool.reduce((n, r) => n + r.count, 0);

  const refresh = useCallback(() => {
    getSealedState().then(setState).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  const act = (fn: () => Promise<SealedAction>) => {
    setBusy(true);
    fn()
      .then((r) => {
        setState(r.state);
        setMessage(r.message);
      })
      .catch((e) => setMessage(String(e)))
      .finally(() => setBusy(false));
  };

  // Separate from act(): draft://refresh only re-reads the built state, so a
  // pool that grew in Arena needs an explicit re-read from the scanner. Returns
  // a bare SealedState rather than the SealedAction act() expects.
  const reloadPool = () => {
    setBusy(true);
    sealedReloadPool()
      .then((s) => {
        setState(s);
        setMessage("Pool reloaded from the Arena log");
      })
      .catch((e) => setMessage(String(e)))
      .finally(() => setBusy(false));
  };

  const addVariant = () => {
    const name = window.prompt("New build name?");
    if (name) act(() => sealedCreateVariant(name));
  };

  const renameVariant = (old: string) => {
    const name = window.prompt("Rename build to?", old);
    if (name && name !== old) act(() => sealedRenameVariant(old, name));
  };

  const importDeck = () => {
    const text = window.prompt("Paste an MTGA decklist:");
    if (text) act(() => sealedImportDeck(text));
  };

  const share = () => {
    setBusy(true);
    sealedExportSealeddeck()
      .then((r) => {
        setShareUrl(r.url);
        setMessage(r.ok ? "Shared to sealeddeck.tech" : r.message);
        if (!r.ok && r.text) navigator.clipboard?.writeText(r.text);
      })
      .catch((e) => setMessage(String(e)))
      .finally(() => setBusy(false));
  };

  const startedPractice = (r: SealedAction) => {
    setState(r.state);
    setMessage(r.message);
    setShareUrl("");
  };

  const practiceDialog = practiceOpen && (
    <PracticeDialog
      onClose={() => setPracticeOpen(false)}
      onStarted={startedPractice}
    />
  );

  if (state && !state.hasPool) {
    return (
      <div className="empty-state">
        <p>No sealed pool detected. Open a Sealed event in Arena, then rescan.</p>
        <button onClick={reloadPool} disabled={busy}>
          Reload pool
        </button>
        <button onClick={() => setPracticeOpen(true)}>Practice pool...</button>
        {message && <p className="hint">{message}</p>}
        {practiceDialog}
      </div>
    );
  }

  return (
    <div className="deck-layout">
      <div className="deck-main">
        <section className="panel">
          <div className="variant-tabs">
            {(state?.variants ?? []).map((v) => (
              <span
                key={v.name}
                className={`variant-tab${v.isActive ? " active" : ""}`}
              >
                <button onClick={() => act(() => sealedSelectVariant(v.name))}>
                  {v.name} <em>({v.mainCount})</em>
                </button>
                <button
                  className="variant-edit"
                  title="Rename"
                  onClick={() => renameVariant(v.name)}
                >
                  ✎
                </button>
                {(state?.variants.length ?? 0) > 1 && (
                  <button
                    className="variant-edit"
                    title="Delete"
                    onClick={() => act(() => sealedDeleteVariant(v.name))}
                  >
                    ✕
                  </button>
                )}
              </span>
            ))}
            <button className="ghost-btn" onClick={addVariant}>
              + Build
            </button>
          </div>
          <div className="deck-toolbar">
            <button onClick={() => act(sealedAutoGenerate)} disabled={busy}>
              Auto-generate shells
            </button>
            <button onClick={() => act(sealedAutoLands)} disabled={busy}>
              Auto-lands
            </button>
            <button onClick={importDeck}>Import</button>
            <button onClick={reloadPool} disabled={busy}>
              Reload pool
            </button>
            <button onClick={() => setPracticeOpen(true)}>Practice...</button>
            <span className="spacer" />
            <button
              className="ghost-btn"
              onClick={() =>
                sealedExport().then((e) => navigator.clipboard?.writeText(e.text))
              }
            >
              Copy export
            </button>
            <button className="ghost-btn" onClick={share} disabled={busy}>
              Share
            </button>
            <button
              className="ghost-btn"
              onClick={() => act(sealedClearDeck)}
            >
              Clear
            </button>
          </div>
          <div className="basics-row">
            <span className="stat-label">Basics:</span>
            {BASICS.map((b) => (
              <span key={b} className="basic-stepper">
                <button
                  className="ghost-btn"
                  onClick={() => act(() => sealedRemoveBasic(b))}
                >
                  −
                </button>
                <span>{state?.stats.basics[b] ?? 0}</span>
                <button
                  className="ghost-btn"
                  onClick={() => act(() => sealedAddBasic(b))}
                >
                  +
                </button>
                <label>{b}</label>
              </span>
            ))}
          </div>
          {message && <div className="sim-note">{message}</div>}
          {shareUrl && (
            <div className="sim-note">
              <a href={shareUrl} target="_blank" rel="noreferrer">
                {shareUrl}
              </a>
            </div>
          )}
        </section>

        <DeckTable
          title="Main deck"
          rows={state?.deck ?? []}
          count={state?.mainCount ?? 0}
          targetCount={40}
          onMove={(name) => act(() => sealedMoveCard(name, true))}
          moveLabel="→ pool"
          emptyText="Auto-generate a shell or double-click a card to add it"
          colorTint={colorTint}
          dblClickMove
          group={deckGroup}
          onGroupChange={setDeckGroup}
        />
        <div className="pool-filter-bar">
          <span className="stat-label">Show:</span>
          {POOL_FILTER_TYPES.map((k) => (
            <label key={k}>
              <input
                type="checkbox"
                checked={poolFilter[k]}
                onChange={(e) =>
                  setPoolFilter({ ...poolFilter, [k]: e.target.checked })
                }
              />
              {k[0].toUpperCase() + k.slice(1)}
            </label>
          ))}
          <span className="pool-filter-divider" />
          {POOL_FILTER_COLORS.map((c) => (
            <label key={c}>
              <input
                type="checkbox"
                checked={poolFilter[c]}
                onChange={(e) =>
                  setPoolFilter({ ...poolFilter, [c]: e.target.checked })
                }
              />
              <span className={`pool-color ${c.toLowerCase()}`}>{c}</span>
            </label>
          ))}
        </div>
        <DeckTable
          title="Pool"
          rows={filteredPool}
          count={filteredPoolCount}
          onMove={(name) => act(() => sealedMoveCard(name, false))}
          moveLabel="↑ main"
          emptyText="Double-click a card to add it to the main deck"
          colorTint={colorTint}
          dblClickMove
          group={poolGroup}
          onGroupChange={setPoolGroup}
        />
      </div>

      <aside className="deck-rail">
        <section className="panel">
          <h2>Deck stats</h2>
          {state && <DeckStatsView stats={state.stats} />}
        </section>
        <section className="panel">
          <h2>Pool</h2>
          <div className="empty-inline">{state?.poolSize ?? 0} cards</div>
        </section>
      </aside>
      {practiceDialog}
    </div>
  );
}
