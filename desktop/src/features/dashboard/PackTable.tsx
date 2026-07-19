import type { Card } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import {
  cardRowClass,
  manaColumn,
  nameColumn,
  statColumns,
} from "../../components/cardColumns";

interface Props {
  cards: Card[];
  colorTint: boolean;
  emptyText?: string;
}

function valueColumn(): Column<Card> {
  return {
    id: "value",
    header: "Value",
    numeric: true,
    cell: (c) =>
      c.recommendation ? c.recommendation.contextualScore.toFixed(0) : "—",
    sortValue: (c) => c.recommendation?.contextualScore ?? -1,
  };
}

export function PackTable({ cards, colorTint, emptyText }: Props) {
  const columns: Column<Card>[] = [
    nameColumn(),
    manaColumn(),
    valueColumn(),
    ...statColumns(),
  ];
  return (
    <DataTable
      columns={columns}
      rows={cards}
      rowKey={(c) => c.name}
      rowClass={(c) => cardRowClass(c, colorTint)}
      defaultSort={{ id: "value", desc: true }}
      emptyText={emptyText ?? "Waiting for a pack..."}
    />
  );
}
