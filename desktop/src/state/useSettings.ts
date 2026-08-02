import { useCallback, useEffect, useState } from "react";

import { getSettings, setSettings } from "../api/client";
import type { Settings, SettingsPatch } from "../api/types";
import { applyTheme, type ThemePreference } from "./theme";

export function useSettings() {
  const [settings, setLocal] = useState<Settings | null>(null);

  const receive = useCallback((next: Settings) => {
    setLocal(next);
    applyTheme(next.desktopTheme as ThemePreference);
  }, []);

  useEffect(() => {
    getSettings().then(receive).catch(console.warn);
  }, [receive]);

  const patch = useCallback(
    async (p: SettingsPatch) => {
      // Optimistic update, replaced by the server's canonical response
      setLocal((prev) => (prev ? { ...prev, ...p } : prev));
      if (p.desktopTheme) applyTheme(p.desktopTheme as ThemePreference);
      try {
        const next = await setSettings(p);
        receive(next);
      } catch (e) {
        console.warn("set_settings failed", e);
        getSettings().then(receive).catch(console.warn);
      }
    },
    [receive],
  );

  return { settings, patch };
}
