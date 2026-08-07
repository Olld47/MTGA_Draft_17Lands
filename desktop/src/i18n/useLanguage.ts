import { useSyncExternalStore } from "react";

import { messages, type Lang } from "./locales";

// Module-level language store, modeled on state/theme.ts: `useSettings` is
// instantiated independently by App and SettingsPage, and every translated
// component subscribes through useLanguage() — the single module instance
// means a setLanguage() in SettingsPage re-renders every consumer.

let lang: Lang = "en";
try {
  const stored = localStorage.getItem("mtga.lang");
  if (stored === "en" || stored === "zh") lang = stored;
} catch {
  // Private mode / disabled storage — default to English.
}

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

/** Sets the active language, mirrors it for index.html's pre-paint script, and
 *  notifies every subscriber. No-op when the language is unchanged. */
export function setLanguage(next: Lang): void {
  if (next === lang) return;
  lang = next;
  document.documentElement.lang = next;
  try {
    localStorage.setItem("mtga.lang", next);
  } catch {
    // Private mode / disabled storage — only costs a flash on the next launch.
  }
  emit();
}

/** Translate a message key for the active language. Falls back to English,
 *  then to the key itself. `vars` interpolates {name} placeholders. */
export function t(key: string, vars?: Record<string, string | number>): string {
  let s = messages[lang][key] ?? messages.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.split(`{${k}}`).join(String(v));
    }
  }
  return s;
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

function snapshot() {
  return lang;
}

export function useLanguage() {
  return {
    lang: useSyncExternalStore(subscribe, snapshot),
    t,
  };
}
