import { useCallback } from "react";

import { useSettings } from "./useSettings";

/** Link shared tables so they inherit each other's sort — the legacy
 *  PerTableWidget._get_sort_group: Main Pack and Mini Pack sort together, as do
 *  Taken and the mini pool. */
export function sortGroup(viewId: string): string {
  if (viewId === "pack_table" || viewId === "overlay_table") return "pack";
  if (viewId === "taken_table" || viewId === "overlay_pool_table") return "pool";
  return viewId;
}

/** Per-table column configuration, persisted through Settings.columnConfigs
 *  (the legacy `column_configs` map). Each card table identifies itself with a
 *  viewId matching the legacy keys (pack_table, taken_table, compare_table,
 *  missing_table, overlay_table, ...); the visible field list is stored per
 *  view and restored on the next load. `defaults` is the fallback the table
 *  renders before the user has ever customized it.
 *
 *  `valid` filters the stored list — legacy configs embed base columns ("name")
 *  and unsupported fields (TIER0…) that the desktop renders outside the config
 *  or not at all, and those must not leak into the visible set.
 *
 *  Also exposes the legacy per-table view state that travels through the same
 *  Settings channel: the column display order (`columnDisplayOrders`, written
 *  by the header drag-to-reorder) and the persisted sort (`tableSortStates`,
 *  restored as the table's initial sort). */
export function useColumnConfig(
  viewId: string,
  defaults: string[],
  valid: (id: string) => boolean = () => true,
) {
  const { settings, patch } = useSettings();

  const stored = settings?.columnConfigs?.[viewId];
  const candidate = stored && stored.length > 0 ? stored : defaults;
  const filtered = candidate.filter(valid);
  const fields = filtered.length > 0 ? filtered : defaults;

  // Display order: the legacy column_display_orders[viewId] is a permutation of
  // the visible configurable fields. Use it when it still matches the current
  // set; otherwise (columns added/removed since) fall back to field order.
  const savedOrder = settings?.columnDisplayOrders?.[viewId];
  const order =
    savedOrder &&
    savedOrder.length === fields.length &&
    savedOrder.every((f) => fields.includes(f))
      ? savedOrder
      : fields;

  const write = useCallback(
    (next: string[]) => {
      patch({
        columnConfigs: {
          ...(settings?.columnConfigs ?? {}),
          [viewId]: next,
        },
      });
    },
    [settings, patch, viewId],
  );

  const writeOrder = useCallback(
    (next: string[]) => {
      patch({
        columnDisplayOrders: {
          ...(settings?.columnDisplayOrders ?? {}),
          [viewId]: next,
        },
      });
    },
    [settings, patch, viewId],
  );

  const add = useCallback(
    (field: string) => {
      if (!fields.includes(field)) write([...fields, field]);
    },
    [fields, write],
  );

  const remove = useCallback(
    (field: string) => write(fields.filter((f) => f !== field)),
    [fields, write],
  );

  const reset = useCallback(() => write(defaults), [defaults, write]);

  /** Move `from` to just before `to` — the legacy display_order.insert(target,
   *  pop(source)) semantics for the header drag. */
  const move = useCallback(
    (from: string, to: string) => {
      const i = order.indexOf(from);
      const j = order.indexOf(to);
      if (i < 0 || j < 0 || i === j) return;
      const next = order.filter((f) => f !== from);
      next.splice(j - (i < j ? 1 : 0), 0, from);
      writeOrder(next);
    },
    [order, writeOrder],
  );

  // Persisted sort state, keyed by the legacy sort group (pack/pool/…).
  const group = sortGroup(viewId);
  const savedSort = settings?.tableSortStates?.[group];
  const initialSort =
    savedSort?.column && savedSort.reverse != null
      ? { id: savedSort.column, desc: savedSort.reverse }
      : undefined;
  const setSort = useCallback(
    (s: { id: string; desc: boolean }) => {
      patch({
        tableSortStates: {
          ...(settings?.tableSortStates ?? {}),
          [group]: { column: s.id, reverse: s.desc },
        },
      });
    },
    [settings, patch, group],
  );

  return { fields, order, add, remove, reset, move, initialSort, setSort };
}
