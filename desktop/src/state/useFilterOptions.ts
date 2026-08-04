import { useCallback, useEffect, useState } from "react";

import { getFilterOptions } from "../api/client";
import { EVENTS, on, type RefreshPayload } from "../api/events";
import type { FilterOptions } from "../api/types";

/** The deck-filter dropdown's contents, from constants.DECK_FILTERS on the
 *  Python side. Refetches on draft://refresh because `autoDetected` tracks the
 *  pool as it grows, and whenever `filterFormat` changes because the labels and
 *  win rates are rendered server-side under that setting. */
export function useFilterOptions(filterFormat?: string) {
  const [options, setOptions] = useState<FilterOptions | null>(null);

  const refresh = useCallback(() => {
    getFilterOptions()
      .then(setOptions)
      .catch((e) => console.warn("get_filter_options failed", e));
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh, filterFormat]);

  return options;
}
