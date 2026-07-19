import { useCallback, useEffect, useState } from "react";

import { getTakenCards } from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { Card, TakenCards } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import {
  cardRowClass,
  manaColumn,
  nameColumn,
  statColumns,
} from "../../components/cardColumns";
import { PoolSummaryStrip } from "../dashboard/PoolSummaryStrip";

function countColumn(): Column<Card> {
  return {
    id: "count",
    header: "#",
    numeric: true,
    cell: (c) => c.count,
    sortValue: (c) => c.count,
  };
}

export function TakenPage({ colorTint }: { colorTint: boolean }) {
  const [taken, setTaken] = useState<TakenCards | null>(null);

  const refresh = useCallback(() => {
    getTakenCards().then(setTaken).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  const columns: Column<Card>[] = [
    countColumn(),
    nameColumn(),
    manaColumn(),
    ...statColumns(),
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      {taken && taken.poolSummary.cardCount > 0 && (
        <section className="panel">
          <h2>Pool</h2>
          <PoolSummaryStrip summary={taken.poolSummary} />
        </section>
      )}
      <section className="panel">
        <h2>Taken cards {taken ? `(${taken.poolSummary.cardCount})` : ""}</h2>
        <DataTable
          columns={columns}
          rows={taken?.cards ?? []}
          rowKey={(c) => c.name}
          rowClass={(c) => cardRowClass(c, colorTint)}
          defaultSort={{ id: "cost", desc: false }}
          emptyText="Cards you draft appear here"
        />
      </section>
    </div>
  );
}
