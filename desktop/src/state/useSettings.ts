import { useCallback, useEffect, useState } from "react";

import { getSettings, setSettings } from "../api/client";
import type { Settings, SettingsPatch } from "../api/types";

export function useSettings() {
  const [settings, setLocal] = useState<Settings | null>(null);

  useEffect(() => {
    getSettings().then(setLocal).catch(console.warn);
  }, []);

  const patch = useCallback(async (p: SettingsPatch) => {
    // Optimistic update, replaced by the server's canonical response
    setLocal((prev) => (prev ? { ...prev, ...p } : prev));
    try {
      const next = await setSettings(p);
      setLocal(next);
    } catch (e) {
      console.warn("set_settings failed", e);
      getSettings().then(setLocal).catch(console.warn);
    }
  }, []);

  return { settings, patch };
}
