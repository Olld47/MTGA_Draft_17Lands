import type { Card } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import {
  artUrl,
  CARD_COLUMN_FIELDS,
  CARD_COLUMN_LABELS,
  cardColumn,
  cardRowClass,
  manaColumn,
  nameColumn,
} from "../../components/cardColumns";
import { useCardMenu } from "../../components/CardContextMenu";
import { useColumnConfig } from "../../state/useColumnConfig";
import { useStatFormat } from "../../state/useStatFormat";

interface Props {
  cards: Card[];
  colorTint: boolean;
  emptyText?: string;
  /** Per-table column-config key (legacy view_id); defaults to the dashboard
   *  pack table. The mini overlay passes overlay_table / missing_table. */
  viewId?: string;
}

/** Default visible fields — the pre-column-config hardcoded columns, so an
 *  uncustomized table renders identically. */
const DEFAULT_FIELDS = ["value", "gihwr", "ohwr", "alsa", "ata", "iwd"];

export function PackTable({
  cards,
  colorTint,
  emptyText,
  viewId = "pack_table",
}: Props) {
  const { resultFormat, metrics } = useStatFormat();
  const format = { resultFormat, metrics };
  const { fields, add, remove, reset } = useColumnConfig(viewId, DEFAULT_FIELDS);

  const columns: Column<Card>[] = [
    nameColumn(),
    manaColumn(),
    ...fields.map((f) => cardColumn(f, format)),
  ];
  const menu = useCardMenu();

  return (
    <>
      <DataTable
        columns={columns}
        rows={cards}
        rowKey={(c) => c.name}
        rowClass={(c) => cardRowClass(c, colorTint)}
        defaultSort={{ id: "value", desc: true }}
        emptyText={emptyText ?? "Waiting for a pack..."}
        hoverImage={(c) => artUrl(c.image)}
        onContextMenu={(c, x, y) => menu.open(c.name, x, y)}
        columnMenu={{
          active: fields,
          addable: CARD_COLUMN_FIELDS.filter((f) => !fields.includes(f)).map(
            (f) => ({ id: f, label: CARD_COLUMN_LABELS[f] }),
          ),
          removable: (id) => fields.includes(id),
          label: (id) => CARD_COLUMN_LABELS[id] ?? id,
          onAdd: add,
          onRemove: remove,
          onReset: reset,
        }}
      />
      {menu.element}
    </>
  );
}
