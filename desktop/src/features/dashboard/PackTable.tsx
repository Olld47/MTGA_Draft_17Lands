import type { Card } from "../../api/types";
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

interface Props {
  cards: Card[];
  colorTint: boolean;
  emptyText?: string;
  /** Per-table column-config key (legacy view_id); defaults to the dashboard
   *  pack table. The mini overlay passes overlay_table / missing_table. */
  viewId?: string;
  /** Initial sort override — the legacy wheel tracker (missing_table) sorts by
   *  GIH WR desc because seen cards carry no advisor value. */
  defaultSort?: { id: string; desc: boolean };
}

/** Default visible fields. Not byte-identical to the legacy 3-column default
 *  (["value", "gihwr"]) — the desktop shows the full stat row by default; every
 *  legacy field is still addable via the column menu. */
const DEFAULT_FIELDS = ["value", "gihwr", "ohwr", "alsa", "ata", "iwd"];

export function PackTable({
  cards,
  colorTint,
  emptyText,
  viewId = "pack_table",
  defaultSort,
}: Props) {
  const { resultFormat, metrics } = useStatFormat();
  const format = { resultFormat, metrics };
  const { t } = useLanguage();
  const { fields, order, add, remove, reset, move, initialSort, setSort } =
    useColumnConfig(
      viewId,
      DEFAULT_FIELDS,
      // Legacy configs embed base columns ("name", "cost") that the desktop
      // renders outside the configurable set — strip them or they'd render a
      // duplicate "name" column (cardColumns' default branch).
      (id) => CARD_COLUMN_FIELDS.includes(id),
    );

  const columns: Column<Card>[] = [
    nameColumn({ colorName: true }, t),
    manaColumn(t),
    ...order.map((f) => cardColumn(f, format, t)),
  ];
  const menu = useCardMenu();

  return (
    <>
      <DataTable
        columns={columns}
        rows={cards}
        rowKey={(c) => c.name}
        rowClass={(c) => cardRowClass(c, colorTint)}
        defaultSort={defaultSort ?? { id: "value", desc: true }}
        initialSort={initialSort}
        onSortChange={setSort}
        emptyText={emptyText ?? t("dash.waitingPack")}
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
      {menu.element}
    </>
  );
}
