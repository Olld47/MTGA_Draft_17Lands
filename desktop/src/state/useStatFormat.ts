import { useSyncExternalStore } from "react";

import { getSetMetrics } from "../api/client";
import { EVENTS, on, type RefreshPayload } from "../api/events";
import type { SetMetrics } from "../api/types";
import { useSettings } from "./useSettings";

// Shared store for the active dataset's win-rate metrics (mean/std per
// field+color) plus the current result_format setting. Metrics are per-dataset,
// so the store refreshes on every draftRefresh (boot, and dataset load/switch
// via select_dataset) — matching how the legacy rebuilds its table values when
// the dataset or setting changes.

let metrics: SetMetrics = { metrics: {}, hasData: false };
let started = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

async function refresh() {
  try {
    metrics = await getSetMetrics();
  } catch (e) {
    // Not booted yet (get_set_metrics requires boot) — a later draftRefresh
    // retries; meanwhile keep the last-known metrics.
    console.warn("get_set_metrics failed", e);
  }
  emit();
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  if (!started) {
    started = true;
    on<RefreshPayload>(EVENTS.draftRefresh, () => void refresh());
    void refresh();
  }
  return () => {
    listeners.delete(fn);
  };
}

function snapshot() {
  return metrics;
}

/** result_format + win-rate metrics for the active dataset. Components using
 *  statColumns() or a GIHWR column call this so their cells re-render when the
 *  setting or dataset changes. */
export function useStatFormat() {
  const { settings } = useSettings();
  return {
    resultFormat: settings?.resultFormat ?? "Percentage",
    metrics: useSyncExternalStore(subscribe, snapshot),
  };
}
