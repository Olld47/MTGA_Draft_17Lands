import { useCallback, useEffect, useState } from "react";

import { getTakenCards } from "../../api/client";
import { EVENTS, on, type RefreshPayload } from "../../api/events";
import type { Card, TakenCards } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import {
  CARD_COLUMN_FIELDS,
  CARD_COLUMN_LABELS,
  cardColumn,
  cardRowClass,
  manaColumn,
  nameColumn,
} from "../../components/cardColumns";
import { CardHoverTip, hoverDataFromCard } from "../../components/CardHover";
import { useCardMenu } from "../../components/CardContextMenu";
import { useLanguage } from "../../i18n/useLanguage";
import { useColumnConfig } from "../../state/useColumnConfig";
import { useStatFormat } from "../../state/useStatFormat";
import { PoolSummaryStrip } from "../dashboard/PoolSummaryStrip";

/** Default visible fields — the pre-column-config hardcoded columns. */
const DEFAULT_FIELDS = ["count", "gihwr", "ohwr", "alsa", "ata", "iwd"];

export function TakenPage({ colorTint }: { colorTint: boolean }) {
  const [taken, setTaken] = useState<TakenCards | null>(null);
  const { resultFormat, metrics } = useStatFormat();
  const format = { resultFormat, metrics };
  const { t, lang } = useLanguage();
  const { fields, order, add, remove, reset, move, initialSort, setSort } =
    useColumnConfig(
      "taken_table",
      DEFAULT_FIELDS,
      (id) => CARD_COLUMN_FIELDS.includes(id),
    );

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
    nameColumn({ colorName: true }, t),
    manaColumn(t),
    ...order.map((f) => cardColumn(f, format, t, lang)),
  ];
  const menu = useCardMenu();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      {taken && taken.poolSummary.cardCount > 0 && (
        <section className="panel">
          <h2>{t("taken.pool")}</h2>
          <PoolSummaryStrip summary={taken.poolSummary} />
        </section>
      )}
      <section className="panel">
        <h2>
          {taken
            ? t("taken.takenCards", { n: taken.poolSummary.cardCount })
            : t("tab.taken")}
        </h2>
        <DataTable
          columns={columns}
          rows={taken?.cards ?? []}
          rowKey={(c) => c.name}
          rowClass={(c) => cardRowClass(c, colorTint)}
          defaultSort={{ id: "cost", desc: false }}
          initialSort={initialSort}
          onSortChange={setSort}
          emptyText={t("taken.empty")}
          hoverContent={(c) => <CardHoverTip data={hoverDataFromCard(c)} />}
          onContextMenu={(c, x, y) => menu.open(c.name, x, y)}
          columnMenu={{
            active: fields,
            addable: CARD_COLUMN_FIELDS.filter((f) => !fields.includes(f)).map(
              (f) => ({ id: f, label: t(CARD_COLUMN_LABELS[f]) }),
            ),
            removable: (id) => fields.includes(id),
            label: (id) => t(CARD_COLUMN_LABELS[id] ?? id),
            onAdd: add,
            onRemove: remove,
            onReset: reset,
            onMove: move,
          }}
        />
      </section>
      {menu.element}
    </div>
  );
}

