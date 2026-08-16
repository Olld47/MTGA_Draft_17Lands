import { useCallback, useEffect, useState } from "react";

import { getDraftRecord, getRecap, openUrl } from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { DraftRecord, Recap, RecapCard, RecapRole } from "../../api/types";
import { roleChip } from "../../components/cardColumns";
import { ManaCurveChart } from "../dashboard/ManaCurveChart";
import { useLanguage } from "../../i18n/useLanguage";
import { navigateTab } from "../../state/navigation";

const fmt = (v: number | null) => (v == null ? "—" : v.toFixed(1));

function CardList({ cards }: { cards: RecapCard[] }) {
  const { t } = useLanguage();
  if (cards.length === 0) return <div className="empty-inline">{t("recap.none")}</div>;
  return (
    <ul className="recap-card-list">
      {cards.map((c) => (
        <li key={c.name}>
          <span className="card-name">{c.name}</span>
          {c.winRate != null && <span className="num">{fmt(c.winRate)}%</span>}
        </li>
      ))}
    </ul>
  );
}

function RoleChips({ roles }: { roles: RecapRole[] }) {
  const { t, lang } = useLanguage();
  if (roles.length === 0) return <div className="empty-inline">{t("recap.none")}</div>;
  return (
    <div className="recap-chips">
      {roles.map((r) => (
        <span key={r.key || r.label}>
          {roleChip(r, lang, t)} <b>{r.count}</b>
        </span>
      ))}
    </div>
  );
}

/** A steal/reach line: "P1P5 · ALSA 7.2 · +2.3". Legacy dashboard_recap.py
 *  formats steals positive (pick − ALSA) and reaches negative (ATA − pick),
 *  with the reference stat next to each. */
function PickLine({ p, kind }: { p: { pack: number; pick: number; reference: number; delta: number }; kind: "steal" | "reach" }) {
  const { t } = useLanguage();
  const ref = kind === "steal" ? t("col.alsa") : t("col.ata");
  const sign = kind === "steal" ? "+" : "-";
  return (
    <span className="num">
      P{p.pack}p{p.pick} · {ref} {p.reference.toFixed(1)} · {sign}
      {p.delta.toFixed(1)}
    </span>
  );
}

export function RecapPage({ idealCurve = [] }: { idealCurve?: number[] }) {
  const { t } = useLanguage();
  const [recap, setRecap] = useState<Recap | null>(null);
  const [record, setRecord] = useState<DraftRecord | null>(null);

  const refresh = useCallback(() => {
    getRecap()
      .then((r) => {
        setRecap(r);
        if (r.draftId) {
          getDraftRecord(r.draftId).then(setRecord).catch(() => setRecord(null));
        }
      })
      .catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  if (!recap || !recap.hasData) {
    return <div className="empty-state">{t("recap.empty")}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      <section className="panel recap-hero">
        <div className={`recap-grade tint-${recap.gradeStyle}`}>
          <span className="grade-label">{recap.grade}</span>
          <span className="grade-power">{recap.poolPower.toFixed(1)}</span>
        </div>
        <div className="recap-hero-stats">
          <div>
            <span className="stat-label">{t("recap.top23")}</span>
            <span className="stat-value">{fmt(recap.top23Avg)}%</span>
          </div>
          <div>
            <span className="stat-label">{t("recap.formatAvg")}</span>
            <span className="stat-value">{fmt(recap.formatAvg)}%</span>
          </div>
          {record?.found && (
            <div>
              <span className="stat-label">{t("recap.trophy")}</span>
              <span className="stat-value">
                {record.url ? (
                  // Open through the open_url bridge: a bare target=_blank
                  // anchor stays inside the Tauri webview instead of the OS
                  // browser (CardContextMenu uses the same bridge).
                  <a
                    href={record.url}
                    onClick={(e) => {
                      e.preventDefault();
                      openUrl(record.url).catch(console.warn);
                    }}
                  >
                    {record.wins}–{record.losses}
                  </a>
                ) : (
                  `${record.wins}–${record.losses}`
                )}
              </span>
            </div>
          )}
        </div>
        {recap.isSealed && (
          // Legacy dashboard_recap.py packs a "⚔️ Enter Sealed Studio" button
          // into the recap header for Sealed events — a natural hop from the
          // recap into tuning the pool (App subscribes to the nav bus).
          <button className="sealed-studio-btn" onClick={() => navigateTab("sealed")}>
            {t("recap.enterSealed")}
          </button>
        )}
      </section>

      <div className="recap-grid">
        <section className="panel">
          <h2>{t("recap.bestCards")}</h2>
          <CardList cards={recap.bestCards} />
        </section>

        <section className="panel">
          <h2>{t("recap.staples")}</h2>
          <CardList cards={recap.staples} />
        </section>

        <section className="panel">
          <h2>{t("dash.poolBalance")}</h2>
          {Object.keys(recap.typeCounts).length === 0 ? (
            <div className="empty-inline">{t("recap.none")}</div>
          ) : (
            <div className="recap-chips">
              {Object.entries(recap.typeCounts).map(([type, count]) => (
                <span key={type}>
                  {t(`type.${type.toLowerCase()}`)} <b>{count}</b>
                </span>
              ))}
            </div>
          )}
        </section>

        <section className="panel">
          <h2>{t("dash.manaCurve")}</h2>
          <ManaCurveChart
            distribution={recap.cmcDistribution}
            ideal={idealCurve}
          />
        </section>

        <section className="panel">
          <h2>{t("recap.bestArchetypes")}</h2>
          {recap.archetypes.length === 0 ? (
            <div className="empty-inline">{t("recap.none")}</div>
          ) : (
            <ul className="recap-card-list">
              {recap.archetypes.map((a) => (
                <li key={a.name}>
                  <span className="card-name">{a.name}</span>
                  {a.winRate != null && (
                    <span className="num">{fmt(a.winRate)}%</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>{recap.isSealed ? t("recap.steals") : t("recap.stealsLate")}</h2>
          {recap.steals.length === 0 ? (
            <div className="empty-inline">{t("recap.none")}</div>
          ) : (
            <ul className="recap-card-list">
              {recap.steals.map((p) => (
                <li key={`${p.name}-${p.pack}-${p.pick}`}>
                  <span className="card-name">{p.name}</span>
                  <PickLine p={p} kind="steal" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>{t("recap.reaches")}</h2>
          {recap.reaches.length === 0 ? (
            <div className="empty-inline">{t("recap.none")}</div>
          ) : (
            <ul className="recap-card-list">
              {recap.reaches.map((p) => (
                <li key={`${p.name}-${p.pack}-${p.pick}`}>
                  <span className="card-name">{p.name}</span>
                  <PickLine p={p} kind="reach" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>{t("recap.tribes")}</h2>
          <RoleChips roles={recap.tribes} />
        </section>

        <section className="panel">
          <h2>{t("recap.roles")}</h2>
          <RoleChips roles={recap.roles} />
        </section>

        <section className="panel">
          <h2>{t("recap.bombs")}</h2>
          <CardList cards={recap.rares} />
        </section>

        <section className="panel">
          <h2>{t("recap.fixing")}</h2>
          <CardList cards={recap.nonBasicLands} />
        </section>
      </div>
    </div>
  );
}
