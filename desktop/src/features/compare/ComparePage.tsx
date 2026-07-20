import { useCallback, useEffect, useRef, useState } from "react";

import {
  compareAddCard,
  compareClear,
  compareRemoveCard,
  getCompareState,
} from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { Card, CompareState } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import {
  cardRowClass,
  manaColumn,
  nameColumn,
  statColumns,
} from "../../components/cardColumns";

function removeColumn(onRemove: (name: string) => void): Column<Card> {
  return {
    id: "remove",
    header: "",
    cell: (c) => (
      <button
        className="ghost-btn"
        title={`Remove ${c.name}`}
        onClick={() => onRemove(c.name)}
      >
        ✕
      </button>
    ),
  };
}

export function ComparePage({ colorTint }: { colorTint: boolean }) {
  const [state, setState] = useState<CompareState | null>(null);
  const [query, setQuery] = useState("");
  const listId = useRef(`compare-names-${Math.round(performance.now())}`);

  const refresh = useCallback(() => {
    getCompareState().then(setState).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  const add = () => {
    const name = query.trim();
    if (!name) return;
    compareAddCard(name)
      .then((s) => {
        setState(s);
        setQuery("");
      })
      .catch(console.warn);
  };

  const remove = (name: string) => {
    compareRemoveCard(name).then(setState).catch(console.warn);
  };

  const columns: Column<Card>[] = [
    nameColumn(),
    manaColumn(),
    ...statColumns(),
    {
      id: "tier",
      header: "Tier",
      cell: (c) => c.tier ?? "—",
      sortValue: (c) => c.tier ?? "",
    },
    removeColumn(remove),
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      <section className="panel">
        <h2>Compare cards</h2>
        <div className="compare-search">
          <input
            list={listId.current}
            value={query}
            placeholder="Search a card to add..."
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <datalist id={listId.current}>
            {(state?.availableNames ?? []).map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
          <button onClick={add} disabled={!query.trim()}>
            Add
          </button>
          <span className="spacer" />
          <button
            className="ghost-btn"
            onClick={() => compareClear().then(setState).catch(console.warn)}
            disabled={!state?.cards.length}
          >
            Clear
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>
          Side by side {state ? `(${state.cards.length})` : ""}
          {state && (
            <span className="filter-note"> · {state.activeFilter}</span>
          )}
        </h2>
        <DataTable
          columns={columns}
          rows={state?.cards ?? []}
          rowKey={(c) => c.name}
          rowClass={(c) => cardRowClass(c, colorTint)}
          emptyText="Add cards above to compare their 17Lands stats"
        />
      </section>
    </div>
  );
}
