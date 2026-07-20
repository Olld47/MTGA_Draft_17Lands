import { useCallback, useEffect, useState } from "react";

import {
  getSealedState,
  sealedAutoGenerate,
  sealedAutoLands,
  sealedClearDeck,
  sealedCreateVariant,
  sealedDeleteVariant,
  sealedExport,
  sealedExportSealeddeck,
  sealedImportDeck,
  sealedMoveCard,
  sealedRenameVariant,
  sealedSelectVariant,
} from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { SealedAction, SealedState } from "../../api/types";
import { DeckStatsView, DeckTable } from "../deck/DeckStatsView";

export function SealedPage({ colorTint }: { colorTint: boolean }) {
  const [state, setState] = useState<SealedState | null>(null);
  const [message, setMessage] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [busy, setBusy] = useState(false);

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

  if (state && !state.hasPool) {
    return (
      <div className="empty-state">
        No sealed pool detected. Open a Sealed event in Arena, then rescan.
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
          onMove={(name) => act(() => sealedMoveCard(name, true))}
          moveLabel="→ pool"
          emptyText="Auto-generate a shell or move cards up from the pool"
          colorTint={colorTint}
        />
        <DeckTable
          title="Pool"
          rows={state?.sideboard ?? []}
          count={state?.sideboardCount ?? 0}
          onMove={(name) => act(() => sealedMoveCard(name, false))}
          moveLabel="↑ main"
          emptyText="Sealed pool is empty"
          colorTint={colorTint}
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
    </div>
  );
}
