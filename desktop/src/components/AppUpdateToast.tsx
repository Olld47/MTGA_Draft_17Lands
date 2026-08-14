import { useEffect, useState } from "react";

import { EVENTS, on, type UpdateAvailablePayload } from "../api/events";
import { openUrl } from "../api/client";
import { useLanguage } from "../i18n/useLanguage";

/** Toast shown when a newer desktop release exists (app_update_notifier.py).
 *  Self-subscribing like DatasetUpdateToast: mounts once next to the other
 *  toasts and listens for update://available for its whole life. The link opens
 *  the Releases page in the OS browser through the open_url bridge — a bare
 *  target=_blank anchor stays inside the Tauri webview (RecapPage pattern). */
export function AppUpdateToast() {
  const { t } = useLanguage();
  const [update, setUpdate] = useState<UpdateAvailablePayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const un = on<UpdateAvailablePayload>(EVENTS.updateAvailable, (p) => {
      if (cancelled) return;
      setUpdate(p);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (!cancelled) setUpdate(null);
      }, 10000);
    });

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      un.then((f) => f());
    };
  }, []);

  if (!update) return null;

  return (
    <div className="update-toast">
      <span>{t("update.available", { version: update.latestVersion })}</span>{" "}
      <a
        href={update.releaseUrl}
        onClick={(e) => {
          e.preventDefault();
          openUrl(update.releaseUrl).catch(console.warn);
        }}
      >
        {t("update.openReleases")}
      </a>
    </div>
  );
}
