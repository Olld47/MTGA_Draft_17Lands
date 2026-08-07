import { useCallback, useEffect, useState } from "react";

import { getDatasetSwitcher } from "../api/client";
import { EVENTS, on, type RefreshPayload } from "../api/events";
import type { DatasetSwitcher } from "../api/types";

const EMPTY: DatasetSwitcher = {
  setCode: "",
  detectedEvent: null,
  activeEvent: null,
  activeGroup: null,
  events: [],
};

/** Event-type / user-group options for the currently detected set. Refetches
 *  on draftRefresh so it tracks the active set and the loaded dataset (both
 *  change alongside draft events). */
export function useDatasetSwitcher() {
  const [switcher, setSwitcher] = useState<DatasetSwitcher>(EMPTY);

  const refresh = useCallback(() => {
    getDatasetSwitcher().then(setSwitcher).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [refresh]);

  return { switcher };
}
