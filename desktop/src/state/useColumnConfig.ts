import { useCallback } from "react";

import { useSettings } from "./useSettings";

/** Per-table column configuration, persisted through Settings.columnConfigs
 *  (the legacy `column_configs` map). Each card table identifies itself with a
 *  viewId matching the legacy keys (pack_table, taken_table, compare_table,
 *  missing_table, overlay_table, ...); the visible field list is stored per
 *  view and restored on the next load. `defaults` is the fallback the table
 *  renders before the user has ever customized it.
 *
 *  `valid` filters the stored list — legacy configs embed base columns ("name")
 *  and unsupported fields (TIER0…) that the desktop renders outside the config
 *  or not at all, and those must not leak into the visible set. */
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

  return { fields, add, remove, reset };
}
