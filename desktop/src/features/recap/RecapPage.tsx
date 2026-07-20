import { useCallback, useEffect, useState } from "react";

import { getDraftRecord, getRecap } from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { DraftRecord, Recap, RecapCard, RecapRole } from "../../api/types";

const fmt = (v: number | null) => (v == null ? "—" : v.toFixed(1));

function CardList({ cards }: { cards: RecapCard[] }) {
  if (cards.length === 0) return <div className="empty-inline">None</div>;
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
  if (roles.length === 0) return <div className="empty-inline">None</div>;
  return (
    <div className="recap-chips">
      {roles.map((r) => (
        <span key={r.label}>
          {r.label} <b>{r.count}</b>
        </span>
      ))}
    </div>
  );
}

export function RecapPage() {
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
    return (
      <div className="empty-state">
        Finish a draft to see your pool recap and grade.
      </div>
    );
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
            <span className="stat-label">Top-23 avg GIHWR</span>
            <span className="stat-value">{fmt(recap.top23Avg)}%</span>
          </div>
          <div>
            <span className="stat-label">Format avg</span>
            <span className="stat-value">{fmt(recap.formatAvg)}%</span>
          </div>
          {record?.found && (
            <div>
              <span className="stat-label">Trophy record</span>
              <span className="stat-value">
                {record.url ? (
                  <a href={record.url} target="_blank" rel="noreferrer">
                    {record.wins}–{record.losses}
                  </a>
                ) : (
                  `${record.wins}–${record.losses}`
                )}
              </span>
            </div>
          )}
        </div>
      </section>

      <div className="recap-grid">
        <section className="panel">
          <h2>Best cards</h2>
          <CardList cards={recap.bestCards} />
        </section>

        <section className="panel">
          <h2>Best archetypes</h2>
          {recap.archetypes.length === 0 ? (
            <div className="empty-inline">None</div>
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
          <h2>Steals {recap.isSealed ? "" : "(late picks)"}</h2>
          {recap.steals.length === 0 ? (
            <div className="empty-inline">None</div>
          ) : (
            <ul className="recap-card-list">
              {recap.steals.map((p) => (
                <li key={`${p.name}-${p.pack}-${p.pick}`}>
                  <span className="card-name">{p.name}</span>
                  <span className="num">
                    P{p.pack}p{p.pick} · +{p.delta.toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>Reaches (early picks)</h2>
          {recap.reaches.length === 0 ? (
            <div className="empty-inline">None</div>
          ) : (
            <ul className="recap-card-list">
              {recap.reaches.map((p) => (
                <li key={`${p.name}-${p.pack}-${p.pick}`}>
                  <span className="card-name">{p.name}</span>
                  <span className="num">
                    P{p.pack}p{p.pick} · {p.delta.toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>Tribes</h2>
          <RoleChips roles={recap.tribes} />
        </section>

        <section className="panel">
          <h2>Roles</h2>
          <RoleChips roles={recap.roles} />
        </section>

        <section className="panel">
          <h2>Bombs &amp; rares</h2>
          <CardList cards={recap.rares} />
        </section>

        <section className="panel">
          <h2>Fixing / lands</h2>
          <CardList cards={recap.nonBasicLands} />
        </section>
      </div>
    </div>
  );
}
