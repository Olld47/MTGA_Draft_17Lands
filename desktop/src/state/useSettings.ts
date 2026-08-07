import { useSyncExternalStore } from "react";

import { getSettings, resetSettings, setSettings } from "../api/client";
import type { Settings, SettingsPatch } from "../api/types";
import { applyTheme, type ThemePreference } from "./theme";

// Module-level shared store: every useSettings() call subscribes to the SAME
// state, so a patch made in SettingsPage re-renders every consumer (App's
// colorTint, the stat tables' resultFormat, ...) instead of living in one
// component's local useState. getSettings is fetched once, on first subscribe.

let settings: Settings | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function receive(next: Settings) {
  settings = next;
  applyTheme(next.desktopTheme as ThemePreference);
  emit();
}

async function ensure() {
  if (loaded) return;
  loaded = true;
  try {
    receive(await getSettings());
  } catch (e) {
    console.warn("get_settings failed", e);
  }
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  if (!loaded) void ensure();
  return () => {
    listeners.delete(fn);
  };
}

function snapshot() {
  return settings;
}

async function patch(p: SettingsPatch) {
  // Optimistic update, replaced by the server's canonical response
  if (settings) {
    settings = { ...settings, ...p };
    if (p.desktopTheme) applyTheme(p.desktopTheme as ThemePreference);
    emit();
  }
  try {
    receive(await setSettings(p));
  } catch (e) {
    console.warn("set_settings failed", e);
    try {
      receive(await getSettings());
    } catch (e2) {
      console.warn("get_settings failed", e2);
    }
  }
}

async function reset() {
  // "Restore Defaults" — the backend rewrites the baseline config and returns
  // it; receive() re-applies the theme and notifies every subscriber.
  try {
    receive(await resetSettings());
  } catch (e) {
    console.warn("reset_settings failed", e);
  }
}

export function useSettings() {
  return {
    settings: useSyncExternalStore(subscribe, snapshot),
    patch,
    reset,
  };
}
