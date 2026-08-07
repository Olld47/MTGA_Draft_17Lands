import { useCallback, useEffect, useState } from "react";

import {
  deckAddBasic,
  deckAutoLands,
  deckAutoOptimize,
  deckClear,
  deckExport,
  deckMoveCard,
  deckRefreshPool,
  deckRemoveBasic,
  deckSampleHand,
  deckSimulate,
} from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { DeckState, SampleHand, SimResult } from "../../api/types";
import { DeckStatsView, DeckTable } from "./DeckStatsView";
import { SampleHandView } from "../../components/SampleHandView";
import { useLanguage } from "../../i18n/useLanguage";
import { SimResultView } from "./SimResultView";

const BASICS = ["Plains", "Island", "Swamp", "Mountain", "Forest"];

export function DeckPage({ colorTint }: { colorTint: boolean }) {
  const { t } = useLanguage();
  const [state, setState] = useState<DeckState | null>(null);
  const [sim, setSim] = useState<SimResult | null>(null);
  const [hand, setHand] = useState<SampleHand | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    // Auto-sync the draft pool into the sideboard: newly drafted cards land in
    // the pool table without a manual "Refresh pool" click (idempotent when the
    // pool hasn't grown — refresh_pool only appends cards beyond the last count).
    deckRefreshPool().then(setState).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  const run = (fn: () => Promise<DeckState>) => {
    fn().then(setState).catch(console.warn);
  };

  const runSim = (fn: () => Promise<SimResult>) => {
    setBusy(true);
    fn()
      .then((r) => {
        setSim(r);
        refresh();
      })
      .catch(console.warn)
      .finally(() => setBusy(false));
  };

  return (
    <div className="deck-layout">
      <div className="deck-main">
        <section className="panel">
          <div className="deck-toolbar">
            <button onClick={() => run(deckRefreshPool)}>
              {t("deck.refreshPool")}
            </button>
            <button onClick={() => runSim(deckAutoOptimize)} disabled={busy}>
              {t("deck.autobuild")}
            </button>
            <button onClick={() => runSim(deckAutoLands)} disabled={busy}>
              {t("deck.autolands")}
            </button>
            <button onClick={() => runSim(deckSimulate)} disabled={busy}>
              {t("deck.simulate")}
            </button>
            <button onClick={() => deckSampleHand().then(setHand)}>
              {t("deck.sampleHand")}
            </button>
            <span className="spacer" />
            <button className="ghost-btn" onClick={() => run(deckClear)}>
              {t("deck.clear")}
            </button>
            <button
              className="ghost-btn"
              onClick={() =>
                deckExport().then((e) => navigator.clipboard?.writeText(e.text))
              }
            >
              {t("deck.copyExport")}
            </button>
          </div>
          <div className="basics-row">
            <span className="stat-label">{t("deck.basics")}</span>
            {BASICS.map((b) => (
              <span key={b} className="basic-stepper">
                <button
                  className="ghost-btn"
                  onClick={() => run(() => deckRemoveBasic(b))}
                >
                  −
                </button>
                <span>{state?.stats.basics[b] ?? 0}</span>
                <button
                  className="ghost-btn"
                  onClick={() => run(() => deckAddBasic(b))}
                >
                  +
                </button>
                <label>{b}</label>
              </span>
            ))}
          </div>
        </section>

        <DeckTable
          title={t("deck.customDeck")}
          rows={state?.deck ?? []}
          count={state?.mainCount ?? 0}
          targetCount={40}
          onMove={(name) => run(() => deckMoveCard(name, true))}
          emptyText={t("deck.emptyAdd")}
          colorTint={colorTint}
          dblClickMove
        />
        <DeckTable
          title={t("deck.sideboard")}
          rows={state?.sideboard ?? []}
          count={state?.sideboardCount ?? 0}
          onMove={(name) => run(() => deckMoveCard(name, false))}
          emptyText={t("deck.emptySideboard")}
          colorTint={colorTint}
          dblClickMove
        />
      </div>

      <aside className="deck-rail">
        <section className="panel">
          <h2>{t("deck.stats")}</h2>
          {state && <DeckStatsView stats={state.stats} />}
        </section>
        {sim && <SimResultView result={sim} />}
        {hand && (
          <section className="panel">
            <h2>{t("deck.sampleHandTitle")}</h2>
            <SampleHandView hand={hand} />
          </section>
        )}
      </aside>
    </div>
  );
}
