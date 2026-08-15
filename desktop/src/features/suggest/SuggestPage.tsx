import { useCallback, useEffect, useState } from "react";

import {
  getSuggestState,
  suggestCalculate,
  suggestExport,
  suggestSampleHand,
  suggestSelectArchetype,
  suggestSendToBuilder,
} from "../../api/client";
import type { DraftState, SampleHand, SuggestState } from "../../api/types";
import { SampleHandView } from "../../components/SampleHandView";
import { DeckStatsView, DeckTable } from "../deck/DeckStatsView";
import { SimResultView } from "../deck/SimResultView";
import { useLanguage } from "../../i18n/useLanguage";

export function SuggestPage({
  colorTint,
  draftState,
  onSentToBuilder,
}: {
  colorTint: boolean;
  draftState: DraftState | null;
  onSentToBuilder: () => void;
}) {
  const { t } = useLanguage();
  const [state, setState] = useState<SuggestState | null>(null);
  const [hand, setHand] = useState<SampleHand | null>(null);
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState("");

  // Re-read the suggestion whenever the draft's pool changes (a new pick, a
  // finished draft, or a different history log) — the backend recomputes its
  // `stale` flag against the current taken-cards pool.
  useEffect(() => {
    getSuggestState().then(setState).catch(console.warn);
  }, [
    draftState?.logName,
    draftState?.takenCount,
    draftState?.pack,
    draftState?.pick,
  ]);

  const build = useCallback(() => {
    setBuilding(true);
    setProgress(t("suggest.initializing"));
    setHand(null);
    suggestCalculate((p) => {
      if (p.kind === "status") setProgress(p.text);
      else if (p.archetype) setProgress(t("suggest.found", { archetype: p.archetype.label }));
    })
      .then((s) => {
        setState(s);
        setProgress("");
      })
      .catch(console.warn)
      .finally(() => setBuilding(false));
  }, [t]);

  // A finished draft (cards taken, no pack in progress) whose suggestion is
  // stale triggers the build automatically — no manual "Build decks" click.
  const finishedDraft =
    !!draftState && draftState.takenCount > 0 && draftState.pack === 0;

  useEffect(() => {
    if (!finishedDraft) return;
    if (building) return;
    if (!state?.stale) return;
    build();
  }, [finishedDraft, building, state?.stale, build]);

  const select = (label: string) => {
    setHand(null);
    suggestSelectArchetype(label).then(setState).catch(console.warn);
  };

  const hasDeck = !!state && state.deck.length > 0;

  return (
    <div className="deck-layout">
      <div className="deck-main">
        <section className="panel">
          <div className="deck-toolbar">
            <button onClick={build} disabled={building}>
              {building ? t("suggest.building") : t("suggest.build")}
            </button>
            <select
              className="archetype-select"
              value={state?.selected ?? ""}
              onChange={(e) => select(e.target.value)}
              disabled={!state || state.archetypes.length === 0}
            >
              {state?.archetypes.length ? (
                state.archetypes.map((a) => (
                  <option key={a.label} value={a.label}>
                    {a.label}
                  </option>
                ))
              ) : (
                <option value="">{t("suggest.noSuggestions")}</option>
              )}
            </select>
            <span className="spacer" />
            <button
              className="ghost-btn"
              disabled={!hasDeck}
              onClick={() => suggestSampleHand().then(setHand).catch(console.warn)}
            >
              {t("deck.sampleHand")}
            </button>
            <button
              className="ghost-btn"
              disabled={!hasDeck}
              onClick={() =>
                suggestSendToBuilder().then(onSentToBuilder).catch(console.warn)
              }
            >
              {t("suggest.sendToBuilder")}
            </button>
            <button
              className="ghost-btn"
              disabled={!hasDeck}
              onClick={() =>
                suggestExport().then((e) => navigator.clipboard?.writeText(e.text))
              }
            >
              {t("deck.copyExport")}
            </button>
          </div>
          {building && progress && <div className="sim-note">{progress}</div>}
          {!building && state?.status && (
            <div className="empty-inline">{state.status}</div>
          )}
          {!building && state?.breakdown && (
            <div className="sim-note">{state.breakdown}</div>
          )}
        </section>

        <DeckTable
          title={t("suggest.mainDeck")}
          rows={state?.deck ?? []}
          count={state?.mainCount ?? 0}
          emptyText={t("suggest.emptyMain")}
          colorTint={colorTint}
        />
        <DeckTable
          title={t("deck.sideboard")}
          rows={state?.sideboard ?? []}
          count={state?.sideboardCount ?? 0}
          emptyText={t("suggest.emptySideboard")}
          colorTint={colorTint}
        />

        {hand && (
          <section className="panel">
            <h2>{t("deck.sampleHandTitle")}</h2>
            <SampleHandView hand={hand} />
          </section>
        )}
      </div>

      <aside className="deck-rail">
        <section className="panel">
          <h2>{t("deck.stats")}</h2>
          {state && <DeckStatsView stats={state.stats} />}
        </section>
        {state?.sim && <SimResultView result={state.sim} />}
      </aside>
    </div>
  );
}
