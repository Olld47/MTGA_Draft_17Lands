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
  cardColumn,
  CARD_COLUMN_FIELDS,
  CARD_COLUMN_LABELS,
  cardRowClass,
  manaColumn,
  nameColumn,
} from "../../components/cardColumns";
import { useCardMenu } from "../../components/CardContextMenu";
import { useColumnConfig } from "../../state/useColumnConfig";
import { useStatFormat } from "../../state/useStatFormat";

/** Default visible fields — the pre-column-config hardcoded columns. */
const DEFAULT_FIELDS = ["gihwr", "ohwr", "alsa", "ata", "iwd", "tier"];

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
  const { resultFormat, metrics } = useStatFormat();
  const format = { resultFormat, metrics };
  const {
    fields,
    order,
    add: addField,
    remove: removeField,
    reset: resetFields,
    move,
    initialSort,
    setSort,
  } = useColumnConfig(
    "compare_table",
    DEFAULT_FIELDS,
    (id) => CARD_COLUMN_FIELDS.includes(id),
  );
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
    ...order.map((f) => cardColumn(f, format)),
    removeColumn(remove),
  ];
  const menu = useCardMenu();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      <section className="panel">
        <h2>Compare Cards</h2>
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
          initialSort={initialSort}
          onSortChange={setSort}
          onContextMenu={(c, x, y) => menu.open(c.name, x, y)}
          showAddColumn={false}
          columnMenu={{
            active: fields,
            addable: CARD_COLUMN_FIELDS.filter((f) => !fields.includes(f)).map(
              (f) => ({ id: f, label: CARD_COLUMN_LABELS[f] }),
            ),
            removable: (id) => fields.includes(id),
            label: (id) => CARD_COLUMN_LABELS[id] ?? id,
            onAdd: addField,
            onRemove: removeField,
            onReset: resetFields,
            onMove: move,
          }}
        />
      </section>
      {menu.element}
    </div>
  );
}
